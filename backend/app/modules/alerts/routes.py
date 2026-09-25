"""HTTP routes for the alerts module.

URLs: /api/v1/alerts/...  and admin screens under /api/v1/admin/alerts/...
Routes stay thin: parse input (schemas.py), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "alerts",
    __name__,
    description="Scheduled reminders, notification settings and penalty estimator",
)
