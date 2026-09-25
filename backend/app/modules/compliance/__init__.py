"""Compliance module: Obligations, compliance calendar, item pages and home dashboard.

Context and contracts: docs/modules/compliance.md
Discovered automatically by app/modules/__init__.py.
"""

from app.modules.compliance.routes import blp
from app.modules.compliance.seed import seed

__all__ = ["blp", "seed"]
