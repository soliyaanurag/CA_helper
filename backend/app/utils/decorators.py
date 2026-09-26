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

Planned: `ca_has_active_access(ca_id, business_id)`, the only way a CA may read a
business's data (true only while an engagement or approved invite is active).
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask_jwt_extended import get_current_user, verify_jwt_in_request

from app.errors import ApiError
from app.models import User
from app.models.enums import UserRole


def current_user() -> User:
    """The logged-in, active user of this request. Call only behind @roles_required."""
    return get_current_user()


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
