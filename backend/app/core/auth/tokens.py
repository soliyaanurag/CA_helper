"""JWT setup: what goes into an access token and how token errors look.

Token contents: `sub` = the user's id (string), `role` = business | ca | admin,
`exp` from JWT_ACCESS_TOKEN_EXPIRES. Every JWT failure returns the standard error
body (app/core/errors.py) with one of these codes:

    401 AUTH_REQUIRED     no token sent
    401 TOKEN_INVALID     malformed token or bad signature
    401 TOKEN_EXPIRED     token past its expiry
    401 ACCOUNT_INACTIVE  valid token, but the user was deactivated or deleted

Any 401 makes the frontend log out.
"""

from flask import jsonify
from flask_jwt_extended import JWTManager, create_access_token

from app.core.auth.models import User
from app.core.auth.services import get_active_user
from app.core.errors import error_body


def issue_access_token(user: User) -> str:
    return create_access_token(identity=str(user.id), additional_claims={"role": user.role.value})


def _error(code: str, message: str):
    return jsonify(error_body(code, message)), 401


def register_jwt_callbacks(jwt: JWTManager) -> None:
    """Load the user on every protected request and format JWT errors."""

    @jwt.user_lookup_loader
    def load_user(_header: dict, payload: dict) -> User | None:
        # Returning None triggers user_lookup_error_loader below.
        return get_active_user(payload["sub"])

    @jwt.user_lookup_error_loader
    def user_not_active(_header: dict, _payload: dict):
        return _error("ACCOUNT_INACTIVE", "This account is inactive. Please log in again.")

    @jwt.unauthorized_loader
    def missing_token(_reason: str):
        return _error("AUTH_REQUIRED", "Please log in.")

    @jwt.invalid_token_loader
    def invalid_token(_reason: str):
        return _error("TOKEN_INVALID", "Your session is invalid. Please log in again.")

    @jwt.expired_token_loader
    def expired_token(_header: dict, _payload: dict):
        return _error("TOKEN_EXPIRED", "Your session has expired. Please log in again.")
