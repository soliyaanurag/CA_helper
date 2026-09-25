"""HTTP routes for the documents module.

URLs: /api/documents/...  and admin screens under /api/admin/documents/...
Routes stay thin: parse input (schemas.py), call services.py, return output.
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "documents",
    __name__,
    url_prefix="/api",
    description="Encrypted document vault and filing-proof OCR",
)
