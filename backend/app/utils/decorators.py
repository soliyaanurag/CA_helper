"""Access control helpers, used on EVERY protected endpoint (CLAUDE.md rule 5).

    @blp.route("/compliance/dashboard")
    class Dashboard(MethodView):
        @roles_required(UserRole.BUSINESS)
        @blp.response(200, DashboardSchema)
        def get(self):
            return services.get_dashboard(current_user())

    @login_required        # any logged-in user, whatever the role (e.g. GET /auth/me)

- No token, a bad or expired token, or a deactivated user -> 401 (app/utils/jwt_handlers.py).
- Logged in with another role -> 403 FORBIDDEN.
- The role is checked against the user row in the database, not only the token
  claim, so a role change takes effect at once.

A CA reads a business's data only through the access checks in marketplace_service
(MA14, CLAUDE.md rule 5). In a CA route, call require_ca_access(business_id) first:

    @roles_required(UserRole.CA)
    def get_client_filings(business_id):
        require_ca_access(business_id)          # 404 unless an ACTIVE engagement
        ...
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask_jwt_extended import get_current_user, verify_jwt_in_request
from sqlalchemy import select

from app.errors import ApiError
from app.extensions import db
from app.models import Business, User
from app.models.enums import UserRole
from app.services import marketplace_service


def current_user() -> User:
    """The logged-in, active user of this request. Call only behind @roles_required."""
    return get_current_user()


def current_business_or_none() -> Business | None:
    """The logged-in business user's registered business, or None before registration."""
    return db.session.scalar(
        select(Business).where(Business.user_id == current_user().id)
    )


def current_business() -> Business:
    """The logged-in business user's registered business. Call only behind
    @roles_required(UserRole.BUSINESS). 404 BUSINESS_NOT_FOUND before registration."""
    business = current_business_or_none()
    if business is None:
        raise ApiError(404, "BUSINESS_NOT_FOUND", "Register your business first.")
    return business


def roles_required(*roles: UserRole) -> Callable:
    """Allow the endpoint only for logged-in users with one of `roles`."""

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Raises for a missing/bad token; loads the user and rejects inactive ones.
            verify_jwt_in_request()
            if current_user().role not in roles:
                raise ApiError(403, "FORBIDDEN", "You do not have access to this page.")
            return view(*args, **kwargs)

        return wrapper

    return decorator


def login_required(view: Callable) -> Callable:
    """Allow the endpoint for any logged-in, active user (every role)."""
    return roles_required(*UserRole)(view)


def require_ca_access(business_id) -> None:
    """Stop unless the logged-in CA has an ACTIVE engagement with this business.

    Answers 404 BUSINESS_NOT_FOUND (not 403), so a CA cannot even find out that a
    business exists. Call only behind @roles_required(UserRole.CA).
    """
    ca_profile_id = marketplace_service.own_profile_id(current_user())
    if ca_profile_id is None or not marketplace_service.ca_has_active_access(
        ca_profile_id, business_id
    ):
        raise ApiError(404, "BUSINESS_NOT_FOUND", "This business was not found.")
