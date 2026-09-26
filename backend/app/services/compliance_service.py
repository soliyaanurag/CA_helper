"""Business logic for the compliance calendar and the business home dashboard."""

from app.models import User


def get_dashboard(user: User) -> dict:
    """Data for the business home dashboard.

    For now only a welcome message; the next deadline, due/overdue counts and the
    penalty estimator come later.
    """
    return {"message": f"Welcome, {user.full_name}"}
