"""Business logic for admin screens: users, CA verification and the service catalog."""

from app.models import User


def get_dashboard(user: User) -> dict:
    """Data for the admin home page.

    For now only a welcome message; pending CA verifications and flagged news come later.
    """
    return {"message": f"Welcome, {user.full_name}"}
