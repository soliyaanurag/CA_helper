"""HTTP routes for the onboarding module.

URLs: /api/onboarding/...  and admin screens under /api/admin/onboarding/...
Routes stay thin: parse input (schemas.py), call services.py, return output.
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "onboarding",
    __name__,
    url_prefix="/api",
    description="Business registration, regulatory profile and NIC code",
)
