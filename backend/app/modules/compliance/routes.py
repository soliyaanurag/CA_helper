"""HTTP routes for the compliance module.

URLs: /api/v1/compliance/...  and admin screens under /api/v1/admin/compliance/...
Routes stay thin: parse input (schemas.py), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "compliance",
    __name__,
    description="Obligations, compliance calendar, item pages and home dashboard",
)
