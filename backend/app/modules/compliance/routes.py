"""HTTP routes for the compliance module.

URLs: /api/compliance/...  and admin screens under /api/admin/compliance/...
Routes stay thin: parse input (schemas.py), call services.py, return output.
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "compliance",
    __name__,
    url_prefix="/api",
    description="Obligations, compliance calendar, item pages and home dashboard",
)
