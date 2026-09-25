"""HTTP routes for the onboarding module.

URLs: /api/v1/onboarding/...  and admin screens under /api/v1/admin/onboarding/...
Routes stay thin: parse input (schemas.py), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "onboarding",
    __name__,
    description="Business registration, regulatory profile and NIC code",
)
