"""HTTP routes for the admin module.

URLs: /api/admin/...
Routes stay thin: parse input (schemas.py), call services.py, return output.
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "admin",
    __name__,
    url_prefix="/api",
    description="Admin: users, CA verification and service catalog",
)
