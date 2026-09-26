"""CA Helper backend application package.

`create_app()` is the Flask application factory. Every entrypoint uses it:

- the `flask` CLI:  `flask --app app run | db upgrade | seed | openapi write`
- the manual dev server: `python main.py`
- the worker:        `python worker.py`
- the test fixtures: `backend/conftest.py`
"""

import logging

from flask import Flask, redirect

from app import cli
from app.config import get_config
from app.core.auth.routes import blp as auth_blp
from app.core.auth.tokens import register_jwt_callbacks
from app.core.errors import register_error_handlers
from app.core.health import blp as health_blp
from app.extensions import api, cors, db, jwt, limiter, migrate
from app.modules import API_PREFIX, register_blueprints


def create_app(config_name: str | None = None) -> Flask:
    """Build and configure a Flask app.

    `config_name` is "development" or "testing".
    If it is None, the APP_ENV environment variable decides.
    """
    config = get_config(config_name)
    # Plain console logging: "time LEVEL logger message". Only the level is configurable.
    logging.basicConfig(
        level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    app = Flask(__name__)
    app.config.from_object(config)

    # Bind the extension objects (created once in extensions.py) to this app.
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    register_jwt_callbacks(jwt)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    limiter.init_app(app)
    api.init_app(app)

    # Routes: the core health check (/api/health, unversioned), core auth
    # (/api/v1/auth/...), then every feature module under /api/v1 (auto-discovered).
    api.register_blueprint(health_blp)
    api.register_blueprint(auth_blp, url_prefix=API_PREFIX)
    register_blueprints(api)

    # The API has no pages of its own, so its bare root opens the API docs instead of
    # a 404. A plain Flask route: it stays out of the OpenAPI spec and generated types.
    app.add_url_rule("/", "root", lambda: redirect("/api/docs"))

    register_error_handlers(app)
    cli.register_commands(app)
    return app
