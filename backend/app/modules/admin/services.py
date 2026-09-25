"""Business logic for the admin module.

Functions here are the module's public interface: routes call them, and other
modules may call the ones listed under "Service functions other modules call" in
docs/modules/admin.md.

Each public function is one unit of work: it validates, changes data and commits
once at its end (or raises ApiError before committing). Helpers that other
functions compose do not commit; their docstrings say so.
"""

from app.core.auth.models import User


def get_dashboard(user: User) -> dict:
    """Data for the admin home page.

    For now only a welcome message; pending CA verifications and flagged news come later.
    """
    return {"message": f"Welcome, {user.full_name}"}
