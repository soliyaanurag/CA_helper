"""Logging for the API, the worker and gunicorn.

Every log line carries two context fields:
    request_id  the current HTTP request's ID (app/core/request_id.py), else "-"
    job         the current worker job's id (backend/worker.py), else "-"

Two formats, chosen by LOG_FORMAT:
    text (default, hybrid mode):
        2026-09-25 14:03:01,123 INFO app.request req=3f2a... job=- GET /api/v1/x 200 12ms
    json (Docker), one object per line:
        {"time": "...", "level": "INFO", "logger": "app.request", "message": "...",
         "request_id": "3f2a...", "job": "-"}

`configure_logging()` is called by create_app(), so the API and the worker share
it; backend/gunicorn.conf.py reuses `build_logging_config()` for gunicorn's own lines.
"""

import json
import logging
import logging.config
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Set by the request-ID middleware and by the worker's job wrapper.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
job_var: ContextVar[str | None] = ContextVar("job", default=None)

TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s req=%(request_id)s job=%(job)s %(message)s"


class ContextFilter(logging.Filter):
    """Adds `request_id` and `job` to every log record that passes a handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        record.job = job_var.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line, easy to search with `docker compose logs | jq`."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "job": getattr(record, "job", "-"),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def build_logging_config(log_format: str = "text", level: str = "INFO") -> dict[str, Any]:
    """A `logging.config.dictConfig` dictionary: one stdout handler on the root logger."""
    formatter: dict[str, Any] = (
        {"()": JsonFormatter} if log_format == "json" else {"format": TEXT_FORMAT}
    )
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"context": {"()": ContextFilter}},
        "formatters": {"default": formatter},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "filters": ["context"],
                "formatter": "default",
            }
        },
        "root": {"level": level.upper(), "handlers": ["console"]},
        "loggers": {
            # The API logs one line per request itself (with the request ID), so the
            # dev server's own access lines would be duplicates.
            "werkzeug": {"level": "WARNING"},
            # The worker logs job start/finish itself (with the job name).
            "apscheduler.executors": {"level": "WARNING"},
            # gunicorn's own lines (startup, worker restarts) use our handler too.
            "gunicorn.error": {"level": level.upper(), "handlers": [], "propagate": True},
            # gunicorn writes access lines whenever a logging config is given; the app
            # already logs each request (with its ID), so drop gunicorn's copies.
            "gunicorn.access": {"level": "WARNING", "handlers": [], "propagate": True},
        },
    }


def configure_logging(log_format: str = "text", level: str = "INFO") -> None:
    logging.config.dictConfig(build_logging_config(log_format, level))
