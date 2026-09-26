"""Routes for the CA marketplace (all under /api/v1).

    GET  /api/v1/marketplace/ca-profile   CA only        the CA's own profile
    PUT  /api/v1/marketplace/ca-profile   CA only        create or update it
    GET  /api/v1/marketplace/cas          business only  list of verified CAs

Each route only checks who is calling, reads the input, calls one function in
app/services/marketplace_service.py and returns its result as JSON.
"""

from flask_smorest import Blueprint

from app.models.enums import UserRole
from app.schemas.marketplace import (
    CaListArgsSchema,
    CaListPageSchema,
    CaProfileInputSchema,
    CaProfileSchema,
)
from app.services import marketplace_service
from app.utils.decorators import current_user, roles_required

# A blueprint is a group of routes. app/routes/__init__.py adds it to the app
# under /api/v1, so "/marketplace/cas" becomes "/api/v1/marketplace/cas".
blp = Blueprint("marketplace", __name__, description="CA profiles and the CA list")


# The logged-in CA reads their own profile.
@blp.route("/marketplace/ca-profile", methods=["GET"])
@roles_required(UserRole.CA)
@blp.response(200, CaProfileSchema)
def get_my_profile():
    user = current_user()
    return marketplace_service.get_own_profile(user)


# The logged-in CA saves their profile (first time or an update).
@blp.route("/marketplace/ca-profile", methods=["PUT"])
@roles_required(UserRole.CA)
@blp.arguments(CaProfileInputSchema)
@blp.response(200, CaProfileSchema)
def save_my_profile(data):
    user = current_user()
    return marketplace_service.save_own_profile(user, **data)


# A business sees the verified CAs, with optional filters and pages.
@blp.route("/marketplace/cas", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(CaListArgsSchema, location="query")
@blp.response(200, CaListPageSchema)
def list_cas(filters):
    return marketplace_service.list_verified_cas(**filters)
