"""HTTP routes for the regulatory module.

URLs: /api/v1/regulatory/...  and admin screens under /api/v1/admin/regulatory/...
Routes stay thin: parse input (schemas.py), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "regulatory",
    __name__,
    description="Regulatory news monitor and admin approval",
)
