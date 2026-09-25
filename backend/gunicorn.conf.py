"""gunicorn settings for the backend container (read automatically from the working dir).

Logging: gunicorn's own lines (startup, worker restarts, errors) go through the same
handler and format as the app's (app/core/logging_config.py), so `docker compose
logs backend` is all JSON when LOG_FORMAT=json. gunicorn's access lines are
switched off there: the app logs one line per request itself, with the request ID.
"""

import os

from app.core.logging_config import build_logging_config

bind = "0.0.0.0:8000"
workers = 2
logconfig_dict = build_logging_config(
    os.getenv("LOG_FORMAT", "text").strip().lower(), os.getenv("LOG_LEVEL", "INFO").strip()
)
