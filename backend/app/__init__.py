"""CA Helper backend: the app factory and everything it wires together.

`create_app()` is used by every entrypoint:

- the dev server:   `python main.py` (the backend service of docker-compose.yml)
- the `flask` CLI:   `flask --app app db upgrade | seed | seed-demo | reset-db`
- the worker:        `python worker.py` (the worker service)
- the tests:         `backend/tests/conftest.py`

Files: models.py (tables), utils.py (shared helpers), ocr.py (reading documents), one
file per feature (auth.py, compliance.py, ...), seed.py and demo_seed.py.
"""

import logging
import os
from datetime import timedelta
from http import HTTPStatus

from flask import Flask, jsonify, redirect
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_smorest import Api, Blueprint
from marshmallow import Schema, fields
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from app import (
    admin,
    alerts,
    assistant,
    auth,
    ca_workspace,
    compliance,
    documents,
    marketplace,
    onboarding,
    regulatory,
)
from app.models import User, db
from app.seed import register_commands
from app.utils import ErrorSchema, default_code, error_body, register_error_handlers

log = logging.getLogger(__name__)


# --- Settings -------------------------------------------------------------------------


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    # Access tokens only (no refresh token); lifetime in minutes.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ.get("JWT_ACCESS_TOKEN_MINUTES", "60")))

    # Fernet key for the encrypted columns and files (app/utils/encryption.py).
    FIELD_ENCRYPTION_KEY = os.environ.get("FIELD_ENCRYPTION_KEY")

    # The largest file anyone may upload (files are stored encrypted in the database).
    MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "5"))
    # Flask refuses bigger requests (413) before reading them; 1 MB of room for the form.
    MAX_CONTENT_LENGTH = (MAX_UPLOAD_MB + 1) * 1024 * 1024

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Email (app/utils/email.py): Mailpit in development.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "1025"))
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "CA Helper <no-reply@ca-helper.local>")
    # True: nothing is sent; messages are kept in app.utils.email.outbox (tests).
    MAIL_SUPPRESS_SEND = False

    # Gemini (app/utils/gemini_client.py). No key: the AI features use their fallback.
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or None
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    GEMINI_EMBED_MODEL = os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001")
    GEMINI_TIMEOUT_SECONDS = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "20"))

    # DEBUG | INFO | WARNING | ERROR
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").strip().upper()

    # OpenAPI docs (flask-smorest)
    API_TITLE = "CA Helper API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/api"
    OPENAPI_JSON_PATH = "openapi.json"  # served at /api/openapi.json
    OPENAPI_SWAGGER_UI_PATH = "/docs"  # Swagger UI at /api/docs
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/"
    API_SPEC_OPTIONS = {
        "info": {"description": "CA Helper (ComplianceConnect) REST API."},
        # Adds the "Authorize" button in Swagger UI for JWT access tokens.
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            }
        },
        # Every endpoint needs a token unless it opts out with @blp.doc(security=[])
        # (health, login). Enforcement is done by app/utils/decorators.py.
        "security": [{"bearerAuth": []}],
    }


# --- Extensions -----------------------------------------------------------------------


class CaHelperApi(Api):
    """flask-smorest Api that formats every HTTP error in our standard shape."""

    ERROR_SCHEMA = ErrorSchema

    def handle_http_exception(self, error: HTTPException):
        status = error.code or 500
        data = getattr(error, "data", None) or {}  # set by flask_smorest.abort(...)
        if "message" in data:
            message = data["message"]
        elif status == 422:
            message = "Some fields are invalid."
        else:
            message = error.description or HTTPStatus(status).phrase
        # Validation errors from flask-smorest/webargs arrive as "errors" or "messages".
        details = data.get("errors") or data.get("messages")
        headers = data.get("headers", {})
        return error_body(default_code(status), message, details), status, headers


migrate = Migrate()
# flask-smorest Api: blueprints, marshmallow schemas, OpenAPI spec, Swagger UI,
# and our JSON error format.
api = CaHelperApi()
jwt = JWTManager()


# --- JWT: load the user for each request and format token errors ------------------------
#
#     401 AUTH_REQUIRED     no token sent
#     401 TOKEN_INVALID     malformed token or bad signature
#     401 TOKEN_EXPIRED     token past its expiry
#     401 ACCOUNT_INACTIVE  valid token, but the account no longer exists
#
# Any 401 makes the frontend log out.


def _jwt_error(code: str, message: str):
    return jsonify(error_body(code, message)), 401


@jwt.user_lookup_loader
def load_user(_header: dict, payload: dict) -> User | None:
    # Returning None triggers user_not_found below.
    return auth.get_user(payload["sub"])


@jwt.user_lookup_error_loader
def user_not_found(_header: dict, _payload: dict):
    return _jwt_error("ACCOUNT_INACTIVE", "This account no longer exists. Please log in again.")


@jwt.unauthorized_loader
def missing_token(_reason: str):
    return _jwt_error("AUTH_REQUIRED", "Please log in.")


@jwt.invalid_token_loader
def invalid_token(_reason: str):
    return _jwt_error("TOKEN_INVALID", "Your session is invalid. Please log in again.")


@jwt.expired_token_loader
def expired_token(_header: dict, _payload: dict):
    return _jwt_error("TOKEN_EXPIRED", "Your session has expired. Please log in again.")


# --- GET /api/health: is the API up and can it reach the database? -------------------

health_blp = Blueprint("health", __name__, url_prefix="/api", description="Service health check")


class HealthSchema(Schema):
    status = fields.String(required=True, metadata={"description": "ok | degraded"})
    database = fields.String(required=True, metadata={"description": "ok | unavailable"})


@health_blp.route("/health")
@health_blp.doc(security=[])  # public: no token needed
@health_blp.response(200, HealthSchema)
@health_blp.alt_response(503, schema=HealthSchema, description="The database is unreachable")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError as exc:
        # One line, not a traceback: this repeats on every check while the db is down.
        cause = getattr(exc, "orig", None) or exc  # the driver's error, e.g. OperationalError
        log.warning("Health check: database unavailable (%s)", type(cause).__name__)
        db.session.rollback()
        database = "unavailable"
    if database == "ok":
        return {"status": "ok", "database": database}
    return {"status": "degraded", "database": database}, 503


# --- The app factory ----------------------------------------------------------------------

# Every feature route lives under this prefix; /api/health, /api/docs and
# /api/openapi.json stay unversioned.
API_PREFIX = "/api/v1"
BLUEPRINTS = [
    auth.bp,
    onboarding.bp,
    compliance.bp,
    ca_workspace.bp,
    marketplace.bp,
    admin.blp,
    alerts.bp,
    documents.bp,
    regulatory.bp,
    assistant.bp,
]


def create_app(test_config: dict | None = None) -> Flask:
    """Build and configure a Flask app. The tests pass `test_config` to replace settings."""
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    # Plain log lines on the terminal: time, level, logger name, message.
    logging.basicConfig(
        level=app.config["LOG_LEVEL"], format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    api.init_app(app)

    api.register_blueprint(health_blp)
    for blp in BLUEPRINTS:
        # Until every feature is plain Flask, flask-smorest registers its own blueprints.
        if isinstance(blp, Blueprint):
            api.register_blueprint(blp, url_prefix=API_PREFIX)
        else:
            app.register_blueprint(blp, url_prefix=API_PREFIX)

    # The API has no pages of its own, so its bare root opens the API docs instead of
    # a 404. A plain Flask route, so it stays out of the OpenAPI spec.
    app.add_url_rule("/", "root", lambda: redirect("/api/docs"))

    register_error_handlers(app)
    register_commands(app)
    return app
