"""CA Helper backend application package.

`create_app()` is the Flask application factory. Every entrypoint uses it:

- the dev server:   `python main.py` (the backend service of docker-compose.yml)
- the `flask` CLI:   `flask --app app db upgrade | seed | seed-demo | reset-db`
- the worker:        `python worker.py` (the worker service)
- the tests:         `backend/tests/conftest.py`

Folders: models/ (tables), schemas/ (request/response shapes), routes/ (HTTP
endpoints), services/ (business logic), utils/ (shared helpers).
"""

import logging

from flask import Flask, redirect

from app.config import Config
from app.errors import register_error_handlers
from app.extensions import api, db, jwt, migrate
from app.routes import register_routes
from app.seed import register_commands
from app.utils.jwt_handlers import register_jwt_callbacks


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

    # Bind the extension objects (created once in extensions.py) to this app.
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    register_jwt_callbacks(jwt)
    api.init_app(app)

    # /api/health, then every feature blueprint under /api/v1 (app/routes/__init__.py).
    register_routes(api)

    # The API has no pages of its own, so its bare root opens the API docs instead of
    # a 404. A plain Flask route, so it stays out of the OpenAPI spec.
    app.add_url_rule("/", "root", lambda: redirect("/api/docs"))

    register_error_handlers(app)
    register_commands(app)
    return app
