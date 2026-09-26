"""CA Helper backend application package.

`create_app()` is the Flask application factory. Every entrypoint uses it:

- the `flask` CLI:  `flask --app app run | db upgrade | seed | openapi write`
- gunicorn (Docker): `gunicorn "app:create_app()"`
- the worker:        `python worker.py`
- the tests:         `backend/tests/conftest.py`

Folders: models/ (tables), schemas/ (request/response shapes), routes/ (HTTP
endpoints), services/ (business logic), utils/ (shared helpers).
"""

from flask import Flask, redirect
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import get_config
from app.errors import register_error_handlers
from app.extensions import api, cors, db, jwt, limiter, migrate
from app.routes import register_routes
from app.seed import register_commands
from app.utils.jwt_handlers import register_jwt_callbacks
from app.utils.logging_setup import configure_logging, init_request_id


def create_app(config_name: str | None = None) -> Flask:
    """Build and configure a Flask app.

    `config_name` is "development", "testing" or "production".
    If it is None, the APP_ENV environment variable decides.
    """
    config = get_config(config_name)
    # Logging first, so every later message (including Flask's) uses our format.
    configure_logging(config.LOG_FORMAT, config.LOG_LEVEL)

    app = Flask(__name__)
    app.config.from_object(config)

    # Behind nginx (Docker), trust one proxy's X-Forwarded-For/-Proto/-Host headers.
    if app.config["TRUST_PROXY"]:
        # (mypy: Flask declares wsgi_app as a method; replacing it is the documented way.)
        app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
            app.wsgi_app, x_for=1, x_proto=1, x_host=1
        )

    # X-Request-ID on every request, response, log line and error body.
    init_request_id(app)

    # Bind the extension objects (created once in extensions.py) to this app.
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    register_jwt_callbacks(jwt)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    limiter.init_app(app)
    api.init_app(app)

    # /api/health, then every feature blueprint under /api/v1 (app/routes/__init__.py).
    register_routes(api)

    # The API has no pages of its own, so its bare root opens the API docs instead of
    # a 404. A plain Flask route: it stays out of the OpenAPI spec and generated types.
    app.add_url_rule("/", "root", lambda: redirect("/api/docs"))

    register_error_handlers(app)
    register_commands(app)
    return app
