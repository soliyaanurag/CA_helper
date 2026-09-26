"""Business logic for the CA's multi-client dashboard and client workspace."""

from app.models import User


def get_dashboard(user: User) -> dict:
    """Data for the CA's multi-client dashboard.

    For now only a welcome message; clients and urgency scores come later.
    """
    return {"message": f"Welcome, {user.full_name}"}
