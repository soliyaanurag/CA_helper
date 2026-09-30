"""Routes for onboarding (all under /api/v1).

    POST /api/v1/onboarding/business   business only   register the business (once)
    GET  /api/v1/onboarding/business   business only   the business with its regulatory profile
    PUT  /api/v1/onboarding/business   business only   edit it (profile recomputed, filings synced)
    GET  /api/v1/onboarding/states     business only   states / UTs with their GST codes
    POST /api/v1/onboarding/nic-suggestions  business only   up to 3 suggested NIC codes
    GET  /api/v1/onboarding/nic-codes?q=     business only   search the NIC list
    PUT  /api/v1/onboarding/business/nic-code  business only  save the confirmed NIC code
    POST /api/v1/onboarding/autofill   business only   read a GST certificate / PAN card (OCR)

Each route only checks who is calling, reads the input, calls one function in
app/services/onboarding_service.py and returns its result as JSON.
"""

from flask_smorest import Blueprint

from app.errors import ErrorSchema
from app.models.enums import UserRole
from app.schemas.onboarding import (
    AutofillSchema,
    BusinessInputSchema,
    GstStateSchema,
    MyBusinessSchema,
    MyBusinessUpdateSchema,
    NicCodeInputSchema,
    NicCodeSchema,
    NicSearchQuerySchema,
    NicSuggestionSchema,
    RegistrationUploadSchema,
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


# Suggest up to 3 NIC activity codes for the business's description (nothing is saved).
# Limited per minute because each call can use the Gemini quota.
@blp.route("/onboarding/nic-suggestions", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, NicSuggestionSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND (register first)")
def suggest_nic_codes():
    return onboarding_service.suggest_nic_codes(current_business())


# Search the official NIC list by code or words, for choosing a code by hand.
@blp.route("/onboarding/nic-codes", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(NicSearchQuerySchema, location="query")
@blp.response(200, NicCodeSchema(many=True))
def search_nic_codes(args):
    return onboarding_service.search_nic_codes(args["q"])


# Save the NIC code the user confirmed.
@blp.route("/onboarding/business/nic-code", methods=["PUT"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(NicCodeInputSchema)
@blp.response(200, NicCodeSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND (register first)")
@blp.alt_response(422, schema=ErrorSchema, description="UNKNOWN_NIC_CODE (not in the list)")
def set_nic_code(data):
    return onboarding_service.set_nic_code(current_business(), data["code"])


# The states and union territories for the form's dropdown.
@blp.route("/onboarding/states", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, GstStateSchema(many=True))
def list_states():
    return onboarding_service.list_states()


# ON13: read a GST certificate or PAN card (locally, not stored) to fill the form.
@blp.route("/onboarding/autofill", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(RegistrationUploadSchema, location="files")
@blp.response(200, AutofillSchema)
@blp.alt_response(
    400, schema=ErrorSchema, description="FILE_EMPTY, FILE_TYPE_NOT_ALLOWED, FILE_TOO_LARGE"
)
@blp.alt_response(422, schema=ErrorSchema, description="DOCUMENT_UNREADABLE")
def autofill(files):
    return onboarding_service.read_registration_document(files["file"])
