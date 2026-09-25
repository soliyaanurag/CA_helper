"""CA Helper backend application package.

`create_app()` is the Flask application factory. Every entrypoint uses it:

- the `flask` CLI:  `flask --app app run | db upgrade | seed | openapi write`
- gunicorn (Docker): `gunicorn "app:create_app()"`
- the worker:        `python worker.py`
- the test fixtures: `backend/conftest.py`
"""

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app import cli
from app.config import get_config
from app.core.errors import register_error_handlers
from app.core.health import blp as health_blp
from app.core.logging_config import configure_logging
from app.core.request_id import init_request_id
from app.extensions import api, cors, db, jwt, limiter, migrate
from app.modules import register_blueprints


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
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    limiter.init_app(app)
    api.init_app(app)

    # Routes: the core health check (/api/health, unversioned for infra healthchecks),
    # then every feature module under /api/v1 (auto-discovered).
    api.register_blueprint(health_blp)
    register_blueprints(api)

    register_error_handlers(app)
    cli.register_commands(app)
    return app
