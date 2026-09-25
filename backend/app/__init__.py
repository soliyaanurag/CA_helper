"""CA Helper backend application package.

`create_app()` is the Flask application factory. Every entrypoint uses it:

- the `flask` CLI:  `flask --app app run | db upgrade | seed | openapi write`
- gunicorn (Docker): `gunicorn "app:create_app()"`
- the worker:        `python worker.py`
- the test fixtures: `backend/conftest.py`
"""

from flask import Flask

from app import cli
from app.config import get_config
from app.core.errors import register_error_handlers
from app.core.health import blp as health_blp
from app.extensions import api, cors, db, jwt, limiter, migrate
from app.modules import register_blueprints


def create_app(config_name: str | None = None) -> Flask:
    """Build and configure a Flask app.

    `config_name` is "development", "testing" or "production".
    If it is None, the APP_ENV environment variable decides.
    """
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    # Bind the extension objects (created once in extensions.py) to this app.
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    limiter.init_app(app)
    api.init_app(app)

    # Routes: the core health check, then every feature module (auto-discovered).
    api.register_blueprint(health_blp)
    register_blueprints(api)

    register_error_handlers(app)
    cli.register_commands(app)
    return app
