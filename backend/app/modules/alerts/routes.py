"""HTTP routes for the alerts module.

URLs: /api/alerts/...  and admin screens under /api/admin/alerts/...
Routes stay thin: parse input (schemas.py), call services.py, return output.
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "alerts",
    __name__,
    url_prefix="/api",
    description="Scheduled reminders, notification settings and penalty estimator",
)
