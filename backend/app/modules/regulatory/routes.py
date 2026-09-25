"""HTTP routes for the regulatory module.

URLs: /api/regulatory/...  and admin screens under /api/admin/regulatory/...
Routes stay thin: parse input (schemas.py), call services.py, return output.
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "regulatory",
    __name__,
    url_prefix="/api",
    description="Regulatory news monitor and admin approval",
)
