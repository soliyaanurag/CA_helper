"""Regulatory module: Regulatory news monitor and admin approval.

Context and contracts: docs/modules/regulatory.md
Discovered automatically by app/modules/__init__.py.
"""

from app.modules.regulatory.routes import blp
from app.modules.regulatory.seed import seed

__all__ = ["blp", "seed"]
