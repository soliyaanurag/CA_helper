"""Request IDs: one ID per HTTP request, in the logs, the response and error bodies.

- If the client (or a proxy) sends a valid `X-Request-ID` header, we reuse it;
  otherwise we generate one (32 hex characters).
- The ID is returned in the `X-Request-ID` response header, added to every log
  line (app/core/logging_config.py) and to every JSON error body
  (app/core/errors.py), so a user-reported error can be found in the logs.
- After each request the API logs one access line: method, path, status, duration.
"""

import logging
import re
import time
import uuid

from flask import Flask, Response, g, request

from app.core.logging_config import request_id_var

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
