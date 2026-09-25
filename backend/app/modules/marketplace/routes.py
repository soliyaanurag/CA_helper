"""HTTP routes for the marketplace module.

URLs: /api/v1/marketplace/...  and admin screens under /api/v1/admin/marketplace/...
Routes stay thin: parse input (schemas.py), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "marketplace",
    __name__,
    description="CA profiles, marketplace, requests and engagements",
)
