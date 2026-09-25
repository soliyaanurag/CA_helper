"""Admin module: Admin: users, CA verification and service catalog.

Owner: Member C. Tasks and contracts: docs/modules/admin.md
Discovered automatically by app/modules/__init__.py.
"""

from app.modules.admin.routes import blp
from app.modules.admin.seed import seed

__all__ = ["blp", "seed"]
