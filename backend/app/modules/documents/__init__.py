"""Documents module: Encrypted document vault and filing-proof OCR.

Context and contracts: docs/modules/documents.md
Discovered automatically by app/modules/__init__.py.
"""

from app.modules.documents.routes import blp
from app.modules.documents.seed import seed

__all__ = ["blp", "seed"]
