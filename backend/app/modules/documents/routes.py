"""HTTP routes for the documents module.

URLs: /api/v1/documents/...  and admin screens under /api/v1/admin/documents/...
Routes stay thin: parse input (schemas.py), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "documents",
    __name__,
    description="Encrypted document vault and filing-proof OCR",
)
