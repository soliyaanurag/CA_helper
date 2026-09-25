"""HTTP routes for the ca_workspace module.

URLs: /api/v1/ca-workspace/...  and admin screens under /api/v1/admin/ca-workspace/...
Routes stay thin: parse input (schemas.py), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "ca_workspace",
    __name__,
    description="CA multi-client dashboard and client workspace",
)
