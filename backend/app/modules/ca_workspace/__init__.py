"""CA workspace module: CA multi-client dashboard and client workspace.

Owner: Member C. Tasks and contracts: docs/modules/ca_workspace.md
Discovered automatically by app/modules/__init__.py.
"""

from app.modules.ca_workspace.routes import blp
from app.modules.ca_workspace.seed import seed

__all__ = ["blp", "seed"]
