"""Onboarding module: Business registration, regulatory profile and NIC code.

Context and contracts: docs/modules/onboarding.md
Discovered automatically by app/modules/__init__.py.
"""

from app.modules.onboarding.routes import blp
from app.modules.onboarding.seed import seed

__all__ = ["blp", "seed"]
