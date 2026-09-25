"""Marketplace module: CA profiles, marketplace, requests and engagements.

Owner: Member C. Tasks and contracts: docs/modules/marketplace.md
Discovered automatically by app/modules/__init__.py.
"""

from app.modules.marketplace.routes import blp
from app.modules.marketplace.seed import seed

__all__ = ["blp", "seed"]
