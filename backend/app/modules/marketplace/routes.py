"""HTTP routes for the marketplace module.

URLs: /api/marketplace/...  and admin screens under /api/admin/marketplace/...
Routes stay thin: parse input (schemas.py), call services.py, return output.
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "marketplace",
    __name__,
    url_prefix="/api",
    description="CA profiles, marketplace, requests and engagements",
)
