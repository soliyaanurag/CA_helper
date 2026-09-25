"""Alerts module: Scheduled reminders, notification settings and penalty estimator.

Owner: Member B. Tasks and contracts: docs/modules/alerts.md
Discovered automatically by app/modules/__init__.py.
"""

from app.modules.alerts.routes import blp
from app.modules.alerts.seed import seed

__all__ = ["blp", "seed"]
