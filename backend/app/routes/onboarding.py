"""Routes for onboarding (all under /api/v1).

    POST /api/v1/onboarding/business   business only   register the business (once)
    GET  /api/v1/onboarding/business   business only   the business with its regulatory profile
    PUT  /api/v1/onboarding/business   business only   edit it (profile recomputed, filings synced)
    GET  /api/v1/onboarding/states     business only   states / UTs with their GST codes

Each route only checks who is calling, reads the input, calls one function in
app/services/onboarding_service.py and returns its result as JSON.
"""

from flask_smorest import Blueprint

from app.errors import ErrorSchema
from app.models.enums import UserRole
from app.schemas.onboarding import (
    BusinessInputSchema,
    GstStateSchema,
    MyBusinessSchema,
    MyBusinessUpdateSchema,
)
from app.services import onboarding_service
from app.utils.decorators import current_business, current_user, roles_required

blp = Blueprint("onboarding", __name__, description="Business registration and regulatory profile")


# A business user registers their business. This also computes the regulatory
# profile and creates the filings of the current financial year.
@blp.route("/onboarding/business", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(BusinessInputSchema)
@blp.response(201, MyBusinessSchema)
@blp.alt_response(409, schema=ErrorSchema, description="BUSINESS_EXISTS (already registered)")
def register_business(data):
    return onboarding_service.register_business(current_user(), data)


# The business user reads their business and its profile (with a "why" per line).
@blp.route("/onboarding/business", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, MyBusinessSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND (register first)")
def get_my_business():
    return onboarding_service.get_my_business(current_business())


# The business user edits their business: the profile is recomputed and this year's
# filings follow it; the answer says what changed.
@blp.route("/onboarding/business", methods=["PUT"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(BusinessInputSchema)
@blp.response(200, MyBusinessUpdateSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND (register first)")
def update_my_business(data):
    return onboarding_service.update_business(current_business(), data)


# The states and union territories for the form's dropdown.
@blp.route("/onboarding/states", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, GstStateSchema(many=True))
def list_states():
    return onboarding_service.list_states()
