"""App settings, read from environment variables.

Docker Compose loads them from the root .env file (see .env.example for what each one
means). The tests replace some of them (tests/conftest.py).
"""

import os
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    # Access tokens only (no refresh token); lifetime in minutes.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ.get("JWT_ACCESS_TOKEN_MINUTES", "60")))

    # Fernet key for the encrypted columns and files (app/utils/encryption.py).
    FIELD_ENCRYPTION_KEY = os.environ.get("FIELD_ENCRYPTION_KEY")

    # Uploaded files (app/utils/storage.py), encrypted, outside the repo's tracked files.
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "instance/uploads")  # relative to backend/
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
