"""Logging for the API, the worker and gunicorn, plus request IDs.

Every log line carries two context fields:
    request_id  the current HTTP request's ID (init_request_id() below), else "-"
    job         the current worker job's id (backend/worker.py), else "-"

Two formats, chosen by LOG_FORMAT:
    text (default, hybrid mode):
        2026-09-25 14:03:01,123 INFO app.request req=3f2a... job=- GET /api/v1/x 200 12ms
    json (Docker), one object per line:
        {"time": "...", "level": "INFO", "logger": "app.request", "message": "...",
         "request_id": "3f2a...", "job": "-"}

`configure_logging()` is called by create_app(), so the API and the worker share
it; backend/gunicorn.conf.py reuses `build_logging_config()` for gunicorn's own lines.

Request IDs (`init_request_id()`):
- If the client (or a proxy) sends a valid `X-Request-ID` header, we reuse it;
  otherwise we generate one (32 hex characters).
- The ID is returned in the `X-Request-ID` response header, added to every log
  line and to every JSON error body (app/errors.py), so a user-reported error
  can be found in the logs.
- After each request the API logs one access line: method, path, status, duration.
"""

import json
import logging
import logging.config
import re
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from flask import Flask, Response, g, request

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


# --- Request IDs ---------------------------------------------------------------

HEADER = "X-Request-ID"
# Accept only short, harmless IDs from outside, so they cannot inject into logs.
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
# Docker polls this every few seconds; its access line is logged at DEBUG only.
_QUIET_PATHS = {"/api/health"}

log = logging.getLogger("app.request")


def get_request_id() -> str | None:
    """The current request's ID, or None outside a request."""
    return request_id_var.get()


def init_request_id(app: Flask) -> None:
    @app.before_request
    def assign_request_id() -> None:
        incoming = request.headers.get(HEADER, "")
        request_id_var.set(incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex)
        g.request_started = time.perf_counter()

    @app.after_request
    def add_header_and_log(response: Response) -> Response:
        request_id = get_request_id()
        if request_id:
            response.headers[HEADER] = request_id
        started = g.get("request_started")
        duration_ms = (time.perf_counter() - started) * 1000 if started else 0.0
        level = logging.DEBUG if request.path in _QUIET_PATHS else logging.INFO
        log.log(
            level,
            "%s %s %s %.0fms",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response

    @app.teardown_request
    def clear_request_id(_exc: BaseException | None) -> None:
        # The thread serves other requests later; do not leak this ID into them.
        request_id_var.set(None)
