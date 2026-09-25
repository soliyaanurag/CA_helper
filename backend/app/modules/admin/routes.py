"""HTTP routes for the admin module.

URLs: /api/v1/admin/...
Routes stay thin: parse input (schemas.py), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "admin",
    __name__,
    description="Admin: users, CA verification and service catalog",
)
