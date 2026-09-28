"""Routes for the CA marketplace (all under /api/v1).

    GET  /api/v1/marketplace/ca-profile   CA only        the CA's own profile
    PUT  /api/v1/marketplace/ca-profile   CA only        create or update it
    GET  /api/v1/marketplace/cas          business only  list of verified CAs
    GET  /api/v1/marketplace/cas/<id>     business only  one verified CA with services and prices
    GET  /api/v1/marketplace/services     logged in      catalog services + typical prices
    GET  /api/v1/marketplace/ca-services  CA only        the services the CA offers, with prices
    PUT  /api/v1/marketplace/ca-services  CA only        replace the CA's price menu

Engagements (a business working with a CA):
    GET  /api/v1/marketplace/cas/<id>/requestable-filings  business  its filings + CA prices
    POST /api/v1/marketplace/engagements                   business  send a request
    GET  /api/v1/marketplace/my-engagements                business  its engagements
    GET  /api/v1/marketplace/ca-engagements                CA        their engagements
    POST /api/v1/marketplace/engagements/<id>/accept       CA        accept at the listed prices
    POST /api/v1/marketplace/engagements/<id>/quote        CA        send new prices with a reason
    POST /api/v1/marketplace/engagements/<id>/decline      CA        decline the request
    POST /api/v1/marketplace/engagements/<id>/complete     CA        mark the work as done
    POST /api/v1/marketplace/engagements/<id>/accept-quote business  accept the CA's quote
    POST /api/v1/marketplace/engagements/<id>/reject-quote business  reject the CA's quote
    POST /api/v1/marketplace/engagements/<id>/withdraw     business  withdraw an unanswered request
    POST /api/v1/marketplace/engagements/<id>/rating       business  rate completed work (MA17)

Pro-bono queue (MA16):
    GET  /api/v1/marketplace/pro-bono                      business  eligibility, request, filings
    POST /api/v1/marketplace/pro-bono                      business  join the queue
    POST /api/v1/marketplace/pro-bono/<id>/cancel          business  leave the queue
    GET  /api/v1/marketplace/pro-bono-queue                CA        pledge, slots used, the queue
    POST /api/v1/marketplace/pro-bono/<id>/accept          CA        take a request (free work)

Each route only checks who is calling, reads the input, calls one function in
app/services/marketplace_service.py and returns its result as JSON.
"""

from flask_smorest import Blueprint

from app.errors import ErrorSchema
from app.models.enums import UserRole
from app.schemas.marketplace import (
    CaDetailSchema,
    CaListArgsSchema,
    CaListPageSchema,
    CaProfileInputSchema,
    CaProfileSchema,
    CaServiceMenuSchema,
    CatalogServiceSchema,
    CertificateUploadSchema,
    EngagementRequestInputSchema,
    EngagementSchema,
    ProBonoJoinInputSchema,
    ProBonoPageSchema,
    ProBonoQueueSchema,
    ProBonoRequestSchema,
    QuoteInputSchema,
    RatingInputSchema,
    RequestableFilingSchema,
)
from app.services import marketplace_service
from app.utils.decorators import current_business, current_user, login_required, roles_required

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


# The logged-in CA uploads their Certificate of Practice (PDF, JPG or PNG). The profile
# then waits for an admin check (`pending`).
@blp.route("/marketplace/ca-profile/certificate", methods=["POST"])
@roles_required(UserRole.CA)
@blp.arguments(CertificateUploadSchema, location="files")
@blp.response(200, CaProfileSchema)
@blp.alt_response(400, schema=ErrorSchema, description="FILE_EMPTY, FILE_TYPE_NOT_ALLOWED, ...")
@blp.alt_response(404, schema=ErrorSchema, description="CA_PROFILE_NOT_FOUND (save it first)")
def upload_certificate(files):
    return marketplace_service.save_certificate(current_user(), files["file"])


# A business sees the verified CAs, with optional filters and pages.
@blp.route("/marketplace/cas", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(CaListArgsSchema, location="query")
@blp.response(200, CaListPageSchema)
def list_cas(filters):
    return marketplace_service.list_verified_cas(**filters, user=current_user())


# A business opens one CA's page: details plus every service they offer with its price.
@blp.route("/marketplace/cas/<uuid:ca_id>", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, CaDetailSchema)
def get_ca(ca_id):
    return marketplace_service.get_verified_ca(ca_id)


# Everyone logged in sees the service catalog with the typical price of each service.
@blp.route("/marketplace/services", methods=["GET"])
@login_required
@blp.response(200, CatalogServiceSchema(many=True))
def list_services():
    return marketplace_service.list_catalog()


# The logged-in CA reads the services they offer and their prices.
@blp.route("/marketplace/ca-services", methods=["GET"])
@roles_required(UserRole.CA)
@blp.response(200, CaServiceMenuSchema)
def get_my_services():
    user = current_user()
    return marketplace_service.get_own_menu(user)


# The logged-in CA saves their whole price menu (it replaces the old one).
@blp.route("/marketplace/ca-services", methods=["PUT"])
@roles_required(UserRole.CA)
@blp.arguments(CaServiceMenuSchema)
@blp.response(200, CaServiceMenuSchema)
def save_my_services(data):
    user = current_user()
    return marketplace_service.save_own_menu(user, data["items"])


# --- Engagements -------------------------------------------------------------------


# The business sees its filings, each with this CA's price, before sending a request.
@blp.route("/marketplace/cas/<uuid:ca_id>/requestable-filings", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, RequestableFilingSchema(many=True))
def list_requestable_filings(ca_id):
    business = current_business()
    return marketplace_service.list_requestable_filings(business, ca_id)


# The business sends a request to a CA for some of its filings.
@blp.route("/marketplace/engagements", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(EngagementRequestInputSchema)
@blp.response(201, EngagementSchema)
def send_request(data):
    business = current_business()
    return marketplace_service.create_request(business, data["ca_profile_id"], data["items"])


# The business sees all its engagements.
@blp.route("/marketplace/my-engagements", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, EngagementSchema(many=True))
def list_my_engagements():
    business = current_business()
    return marketplace_service.list_business_engagements(business)


# The CA sees all their engagements.
@blp.route("/marketplace/ca-engagements", methods=["GET"])
@roles_required(UserRole.CA)
@blp.response(200, EngagementSchema(many=True))
def list_ca_engagements():
    user = current_user()
    return marketplace_service.list_ca_engagements(user)


# --- CA actions on a request ---


@blp.route("/marketplace/engagements/<uuid:engagement_id>/accept", methods=["POST"])
@roles_required(UserRole.CA)
@blp.response(200, EngagementSchema)
def accept_request(engagement_id):
    user = current_user()
    return marketplace_service.accept_request(user, engagement_id)


@blp.route("/marketplace/engagements/<uuid:engagement_id>/quote", methods=["POST"])
@roles_required(UserRole.CA)
@blp.arguments(QuoteInputSchema)
@blp.response(200, EngagementSchema)
def send_quote(data, engagement_id):
    user = current_user()
    return marketplace_service.send_quote(user, engagement_id, data["reason"], data["prices"])


@blp.route("/marketplace/engagements/<uuid:engagement_id>/decline", methods=["POST"])
@roles_required(UserRole.CA)
@blp.response(200, EngagementSchema)
def decline_request(engagement_id):
    user = current_user()
    return marketplace_service.decline_request(user, engagement_id)


@blp.route("/marketplace/engagements/<uuid:engagement_id>/complete", methods=["POST"])
@roles_required(UserRole.CA)
@blp.response(200, EngagementSchema)
def complete_engagement(engagement_id):
    user = current_user()
    return marketplace_service.complete_engagement(user, engagement_id)


# --- Business actions on a request ---


@blp.route("/marketplace/engagements/<uuid:engagement_id>/accept-quote", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, EngagementSchema)
def accept_quote(engagement_id):
    business = current_business()
    return marketplace_service.accept_quote(business, engagement_id)


@blp.route("/marketplace/engagements/<uuid:engagement_id>/reject-quote", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, EngagementSchema)
def reject_quote(engagement_id):
    business = current_business()
    return marketplace_service.reject_quote(business, engagement_id)


@blp.route("/marketplace/engagements/<uuid:engagement_id>/withdraw", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, EngagementSchema)
def withdraw_request(engagement_id):
    business = current_business()
    return marketplace_service.withdraw_request(business, engagement_id)


# The business rates the CA once the work is completed (1 to 5 stars + optional review).
@blp.route("/marketplace/engagements/<uuid:engagement_id>/rating", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(RatingInputSchema)
@blp.response(200, EngagementSchema)
def rate_engagement(data, engagement_id):
    business = current_business()
    return marketplace_service.rate_engagement(
        business, engagement_id, data["stars"], data["review"]
    )


# --- Pro-bono queue (MA16) --------------------------------------------------------------


# The business sees whether it may ask for free help, its queued request and its filings.
@blp.route("/marketplace/pro-bono", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, ProBonoPageSchema)
def get_pro_bono_page():
    business = current_business()
    return marketplace_service.get_pro_bono_page(business)


# The business joins the pro-bono queue with some filings.
@blp.route("/marketplace/pro-bono", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(ProBonoJoinInputSchema)
@blp.response(201, ProBonoRequestSchema)
def join_pro_bono_queue(data):
    business = current_business()
    return marketplace_service.join_pro_bono_queue(
        business, data["compliance_item_ids"], data["note"]
    )


# The business leaves the queue.
@blp.route("/marketplace/pro-bono/<uuid:request_id>/cancel", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, ProBonoRequestSchema)
def cancel_pro_bono_request(request_id):
    business = current_business()
    return marketplace_service.cancel_pro_bono_request(business, request_id)


# The CA sees their pledge, the slots used this month and the queue.
@blp.route("/marketplace/pro-bono-queue", methods=["GET"])
@roles_required(UserRole.CA)
@blp.response(200, ProBonoQueueSchema)
def get_pro_bono_queue():
    user = current_user()
    return marketplace_service.get_pro_bono_queue(user)


# The CA takes a request from the queue: a free engagement starts at once.
@blp.route("/marketplace/pro-bono/<uuid:request_id>/accept", methods=["POST"])
@roles_required(UserRole.CA)
@blp.response(200, EngagementSchema)
def accept_pro_bono_request(request_id):
    user = current_user()
    return marketplace_service.accept_pro_bono_request(user, request_id)
