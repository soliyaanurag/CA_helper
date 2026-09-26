"""X-Request-ID handling, request IDs in logs and error bodies, and the log formats."""

import io
import json
import logging
import re

import pytest

from app import create_app
from app.utils.logging_setup import TEXT_FORMAT, ContextFilter, JsonFormatter, job_var

GENERATED_ID = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture()
def log_output():
    """Collect lines from the `app` loggers, formatted as JSON by our handler setup."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(ContextFilter())
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("app")
    logger.addHandler(handler)
    yield lambda: [json.loads(line) for line in stream.getvalue().splitlines()]
    logger.removeHandler(handler)


def test_incoming_request_id_is_echoed(client):
    response = client.get("/api/openapi.json", headers={"X-Request-ID": "abc-123.x_y"})

    assert response.headers["X-Request-ID"] == "abc-123.x_y"


def test_missing_request_id_is_generated(client):
    response = client.get("/api/openapi.json")

    assert GENERATED_ID.match(response.headers["X-Request-ID"])


@pytest.mark.parametrize("bad_id", ["has space", "a" * 129, "semi;colon", "<script>"])
def test_invalid_incoming_request_id_is_replaced(client, bad_id):
    response = client.get("/api/openapi.json", headers={"X-Request-ID": bad_id})

    assert GENERATED_ID.match(response.headers["X-Request-ID"])


def test_each_request_gets_its_own_id(client):
    first = client.get("/api/openapi.json").headers["X-Request-ID"]
    second = client.get("/api/openapi.json").headers["X-Request-ID"]

    assert first != second


def test_error_body_contains_the_request_id(client):
    response = client.get("/api/v1/does-not-exist", headers={"X-Request-ID": "req-404"})

    assert response.status_code == 404
    assert response.get_json()["error"]["request_id"] == "req-404"


def test_access_log_line_carries_the_request_id(client, log_output):
    client.get("/api/openapi.json", headers={"X-Request-ID": "req-log"})

    lines = [line for line in log_output() if line["logger"] == "app.request"]
    assert lines[-1]["request_id"] == "req-log"
    assert lines[-1]["message"].startswith("GET /api/openapi.json 200")


def test_unhandled_error_gives_500_body_and_log_with_same_request_id(log_output):
    app = create_app("testing")
    app.config["PROPAGATE_EXCEPTIONS"] = False  # behave like production: no traceback

    @app.get("/api/v1/boom")
    def boom():
        raise RuntimeError("boom")

    response = app.test_client().get("/api/v1/boom", headers={"X-Request-ID": "req-500"})

    assert response.status_code == 500
    assert response.get_json()["error"] == {
        "code": "INTERNAL_SERVER_ERROR",
        "message": response.get_json()["error"]["message"],
        "request_id": "req-500",
    }
    exception_lines = [line for line in log_output() if "exception" in line]
    assert exception_lines and exception_lines[-1]["request_id"] == "req-500"
    assert "RuntimeError: boom" in exception_lines[-1]["exception"]


def test_log_lines_outside_requests_use_a_dash():
    record = logging.LogRecord("app.x", logging.INFO, __file__, 1, "hello", None, None)
    ContextFilter().filter(record)

    assert (record.request_id, record.job) == ("-", "-")


def test_text_format_shows_request_id_and_job():
    record = logging.LogRecord("app.x", logging.INFO, __file__, 1, "hello", None, None)
    token = job_var.set("alerts.due_reminders")
    try:
        ContextFilter().filter(record)
    finally:
        job_var.reset(token)

    line = logging.Formatter(TEXT_FORMAT).format(record)

    assert line.endswith("INFO app.x req=- job=alerts.due_reminders hello")


def test_json_format_is_one_json_object_per_line():
    record = logging.LogRecord("app.x", logging.WARNING, __file__, 1, "a %s", ("b",), None)
    ContextFilter().filter(record)

    entry = json.loads(JsonFormatter().format(record))

    assert entry["level"] == "WARNING"
    assert entry["logger"] == "app.x"
    assert entry["message"] == "a b"
    assert entry["request_id"] == "-"
    assert entry["time"].endswith("+00:00")
