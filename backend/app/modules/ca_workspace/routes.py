"""HTTP routes for the ca_workspace module.

URLs: /api/ca-workspace/...  and admin screens under /api/admin/ca-workspace/...
Routes stay thin: parse input (schemas.py), call services.py, return output.
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "ca_workspace",
    __name__,
    url_prefix="/api",
    description="CA multi-client dashboard and client workspace",
)
