"""JSON error format for the whole API (see docs/API_CONVENTIONS.md).

Every error response has this shape:

    {"error": {"code": "NOT_FOUND", "message": "Business not found.", "details": {...},
               "request_id": "3f2a..."}}

- `code` is a stable UPPER_SNAKE_CASE string the frontend can switch on.
- `message` is human-readable.
- `details` is optional, e.g. field validation errors for 422.
- `request_id` is the request's ID (app/core/request_id.py), also in the
  `X-Request-ID` response header and in every log line of that request.

How errors reach this format:
- `raise ApiError(409, "DUPLICATE_PAN", "A business with this PAN already exists.")`
  for expected domain errors in services and routes;
- `flask_smorest.abort(404, message="...")` or any werkzeug HTTPException;
- request validation errors (422) produced automatically by flask-smorest;
- unhandled exceptions become 500 INTERNAL_SERVER_ERROR. With the debugger on
  (`make dev-backend`) and in tests, you see the real traceback instead.
"""

from http import HTTPStatus
from typing import Any

import marshmallow as ma
from flask import Flask
from flask_smorest import Api
from werkzeug.exceptions import HTTPException

from app.core.request_id import get_request_id


class ApiError(Exception):
    """An expected error with a specific HTTP status and error code."""

    def __init__(
        self, status: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict:
    """Build the standard error payload (with the request ID when inside a request)."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    request_id = get_request_id()
    if request_id:
        error["request_id"] = request_id
    return {"error": error}


def default_code(status: int) -> str:
    """Default error code for an HTTP status, e.g. 404 -> "NOT_FOUND"."""
    if status == 422:
        return "VALIDATION_ERROR"
    try:
        return HTTPStatus(status).name
    except ValueError:
        return "ERROR"


class ErrorDetailSchema(ma.Schema):
    code = ma.fields.String(required=True, metadata={"description": "Stable error code"})
    message = ma.fields.String(required=True, metadata={"description": "Human-readable text"})
    details = ma.fields.Dict(metadata={"description": "Extra data, e.g. field errors"})
    request_id = ma.fields.String(
        metadata={"description": "ID of the request; also in the X-Request-ID header and the logs"}
    )


class ErrorSchema(ma.Schema):
    """Documents the error payload in the OpenAPI spec."""

    error = ma.fields.Nested(ErrorDetailSchema, required=True)


class CaHelperApi(Api):
    """flask-smorest Api that formats every HTTP error in our standard shape."""

    ERROR_SCHEMA = ErrorSchema

    def handle_http_exception(self, error: HTTPException):
        status = error.code or 500
        data = getattr(error, "data", None) or {}  # set by flask_smorest.abort(...)
        if "message" in data:
            message = data["message"]
        elif status == 422:
            message = "Some fields are invalid."
        else:
            message = error.description or HTTPStatus(status).phrase
        # Validation errors from flask-smorest/webargs arrive as "errors" or "messages".
        details = data.get("errors") or data.get("messages")
        headers = data.get("headers", {})
        return error_body(default_code(status), message, details), status, headers


def register_error_handlers(app: Flask) -> None:
    """Register handlers for our own exception types (HTTP errors are handled by CaHelperApi)."""

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return error_body(error.code, error.message, error.details), error.status
