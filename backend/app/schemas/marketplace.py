"""Request and response shapes for /api/v1/marketplace/..."""

from marshmallow import Schema, ValidationError, fields, post_load, validate

from app.models.compliance import ComplianceStatus
from app.models.enums import FormCode
from app.models.marketplace import (
    CA_LANGUAGES,
    CA_SPECIALIZATIONS,
    CaVerificationStatus,
    EngagementStatus,
    ProBonoRequestStatus,
    ServiceUnit,
)
from app.schemas.pagination import PageArgsSchema, PageSchema


def _not_blank(value: str) -> None:
    if not value.strip():
        raise ValidationError("Must not be blank.")


def _code_list(codes: tuple[str, ...], what: str) -> fields.List:
    """A non-empty list of known codes, e.g. ["itr", "gstr_1"]."""
    return fields.List(
        fields.String(validate=validate.OneOf(codes)),
        required=True,
        validate=validate.Length(min=1, error=f"Choose at least one {what}."),
    )


def _in_list_order(all_codes: tuple, chosen: list) -> list:
    """The chosen codes once each, in the order of `all_codes` (e.g. CA_LANGUAGES)."""
    result = []
    for code in all_codes:
        if code in chosen:
            result.append(code)
    return result


class CaProfileInputSchema(Schema):
    """PUT /marketplace/ca-profile: everything the CA fills in."""

    membership_no = fields.String(
        required=True,
        validate=validate.Regexp(r"^[0-9]{6}$", error="Enter your 6-digit ICAI membership number."),
    )
    cop_number = fields.String(required=True, validate=[validate.Length(1, 20), _not_blank])
    city = fields.String(required=True, validate=[validate.Length(1, 100), _not_blank])
    languages = _code_list(CA_LANGUAGES, "language")
    specializations = _code_list(CA_SPECIALIZATIONS, "specialization")
    capacity = fields.Integer(required=True, validate=validate.Range(1, 1000))
    years_experience = fields.Integer(required=True, validate=validate.Range(0, 70))
    about = fields.String(load_default="", validate=validate.Length(max=500))
    # Free (pro-bono) engagements the CA takes each month. Not sent -> the saved number stays.
    pro_bono_slots_per_month = fields.Integer(load_default=None, validate=validate.Range(0, 1000))

    @post_load
    def _clean(self, data: dict, **kwargs) -> dict:
        """Trim text; store each code once, in a fixed order."""
        for key in ("cop_number", "city", "about"):
            data[key] = data[key].strip()
        data["languages"] = _in_list_order(CA_LANGUAGES, data["languages"])
        data["specializations"] = _in_list_order(CA_SPECIALIZATIONS, data["specializations"])
        return data


class CaProfileSchema(Schema):
    """The CA's own profile, including the numbers and the verification status."""

    id = fields.UUID(required=True)
    membership_no = fields.String(required=True)
    cop_number = fields.String(required=True)
    city = fields.String(required=True)
    languages = fields.List(fields.String(), required=True)
    specializations = fields.List(fields.String(), required=True)
    capacity = fields.Integer(required=True)
    years_experience = fields.Integer(required=True)
    about = fields.String(required=True)
    verification_status = fields.String(validate=validate.OneOf(list(CaVerificationStatus)), required=True)
    updated_at = fields.DateTime(required=True)
    pro_bono_slots_per_month = fields.Integer(required=True)
    rejection_reason = fields.String(allow_none=True)  # set by an admin when rejecting
    has_certificate = fields.Method("_has_certificate")

    def _has_certificate(self, profile) -> bool:
        return profile.cop_document_id is not None


class CertificateUploadSchema(Schema):
    """POST /marketplace/ca-profile/certificate (multipart/form-data)."""

    file = fields.Raw(required=True, metadata={"type": "string", "format": "binary"})


class CaListArgsSchema(PageArgsSchema):
    """GET /marketplace/cas filters; all optional."""

    specialization = fields.String(validate=validate.OneOf(CA_SPECIALIZATIONS))
    language = fields.String(validate=validate.OneOf(CA_LANGUAGES))
    city = fields.String(validate=validate.Length(max=100))
    # A catalog service code, e.g. "gstr_3b": only CAs who offer it, with their price.
    service = fields.String(validate=validate.Length(max=50))


class RatingSchema(Schema):
    """One rating: 1 to 5 stars and an optional review. Never shows who wrote it."""

    stars = fields.Integer(required=True)
    review = fields.String(allow_none=True)
    created_at = fields.DateTime(required=True)


class CaListItemSchema(Schema):
    """A verified CA as businesses see them (no CoP number, no capacity)."""

    id = fields.UUID(required=True)
    full_name = fields.String(required=True)
    membership_no = fields.String(required=True)
    city = fields.String(required=True)
    languages = fields.List(fields.String(), required=True)
    specializations = fields.List(fields.String(), required=True)
    years_experience = fields.Integer(required=True)
    about = fields.String(required=True)
    # The CA's price for the `service` filter; null when no service is chosen.
    price = fields.Decimal(as_string=True, places=2, allow_none=True)
    # The average of the CA's ratings (one decimal), null before the first rating.
    rating_average = fields.Float(allow_none=True)
    rating_count = fields.Integer(required=True)


class CaListPageSchema(PageSchema):
    items = fields.List(fields.Nested(CaListItemSchema), required=True)


# --- Service catalog and CA prices ------------------------------------------------

MAX_PRICE = 1000000  # rupees; a higher price is almost certainly a typing mistake


class CatalogServiceSchema(Schema):
    """A catalog service and its typical price range across verified CAs.

    The min / median / max prices are null until at least
    marketplace_service.MIN_CAS_FOR_RANGE CAs offer the service.
    """

    id = fields.UUID(required=True)
    code = fields.String(required=True)
    name = fields.String(required=True)
    description = fields.String(required=True)
    unit = fields.String(validate=validate.OneOf(list(ServiceUnit)), required=True)
    # The CA specialization this service belongs to (null: none).
    specialization = fields.String(allow_none=True)
    ca_count = fields.Integer(required=True, metadata={"description": "Verified CAs offering it"})
    min_price = fields.Decimal(as_string=True, places=2, allow_none=True)
    median_price = fields.Decimal(as_string=True, places=2, allow_none=True)
    max_price = fields.Decimal(as_string=True, places=2, allow_none=True)


class CaServicePriceSchema(Schema):
    """One service the CA offers and their price for it."""

    service_id = fields.UUID(required=True)
    price = fields.Decimal(
        as_string=True,
        places=2,
        required=True,
        validate=validate.Range(min=1, max=MAX_PRICE, error="Enter a price from 1 to 10,00,000."),
    )


class CaServiceMenuSchema(Schema):
    """The CA's whole price menu. Saving it replaces the old one."""

    items = fields.List(fields.Nested(CaServicePriceSchema), required=True)


class CaOfferedServiceSchema(CatalogServiceSchema):
    """A catalog service a CA offers: the typical range plus this CA's price."""

    price = fields.Decimal(as_string=True, places=2, required=True)


class CaDetailSchema(Schema):
    """One verified CA's public page (no CoP number, no capacity)."""

    id = fields.UUID(required=True)
    full_name = fields.String(required=True)
    membership_no = fields.String(required=True)
    city = fields.String(required=True)
    languages = fields.List(fields.String(), required=True)
    specializations = fields.List(fields.String(), required=True)
    years_experience = fields.Integer(required=True)
    about = fields.String(required=True)
    services = fields.List(fields.Nested(CaOfferedServiceSchema), required=True)
    rating_average = fields.Float(allow_none=True)
    rating_count = fields.Integer(required=True)
    # The latest ratings, newest first (anonymous).
    reviews = fields.List(fields.Nested(RatingSchema), required=True)


# --- Engagements ---------------------------------------------------------------------


def _money(**kwargs) -> fields.Decimal:
    """Rupees, sent as a string with two decimals ("750.00")."""
    return fields.Decimal(as_string=True, places=2, **kwargs)


class FilingServiceOptionSchema(Schema):
    """One of the CA's services that can do a filing, with the CA's price."""

    service_id = fields.UUID(required=True)
    name = fields.String(required=True)
    price = _money(required=True)


class RequestableFilingSchema(Schema):
    """One of the business's filings on the "Request this CA" page."""

    id = fields.UUID(required=True)
    form_code = fields.String(validate=validate.OneOf(list(FormCode)), required=True)
    period_label = fields.String(required=True)
    due_date = fields.Date(required=True)
    status = fields.String(validate=validate.OneOf(list(ComplianceStatus)), required=True)
    options = fields.List(fields.Nested(FilingServiceOptionSchema), required=True)
    # Why it cannot be picked ("Already filed." ...); null when it can.
    blocked_reason = fields.String(allow_none=True)


class RequestItemInputSchema(Schema):
    compliance_item_id = fields.UUID(required=True)
    service_id = fields.UUID(required=True)


class EngagementRequestInputSchema(Schema):
    """POST /marketplace/engagements: the CA and the filings the business picked."""

    ca_profile_id = fields.UUID(required=True)
    items = fields.List(
        fields.Nested(RequestItemInputSchema),
        required=True,
        validate=validate.Length(min=1, error="Choose at least one filing."),
    )


class EngagementItemSchema(Schema):
    """One filing in an engagement, with its prices."""

    id = fields.UUID(required=True)
    compliance_item_id = fields.UUID(required=True)
    form_code = fields.String(validate=validate.OneOf(list(FormCode)), allow_none=True)
    period_label = fields.String(allow_none=True)
    due_date = fields.Date(allow_none=True)
    service_name = fields.String(required=True)
    listed_price = _money(required=True)
    quoted_price = _money(allow_none=True)
    agreed_price = _money(allow_none=True)


class EngagementSchema(Schema):
    """One engagement between a business and a CA."""

    id = fields.UUID(required=True)
    status = fields.String(validate=validate.OneOf(list(EngagementStatus)), required=True)
    ca_profile_id = fields.UUID(required=True)
    ca_name = fields.String(required=True)
    business_name = fields.String(required=True)
    quote_reason = fields.String(allow_none=True)
    requested_at = fields.DateTime(required=True)
    expires_at = fields.DateTime(allow_none=True)
    responded_at = fields.DateTime(allow_none=True)
    activated_at = fields.DateTime(allow_none=True)
    completed_at = fields.DateTime(allow_none=True)
    items = fields.List(fields.Nested(EngagementItemSchema), required=True)
    # The business's rating once it rated the completed engagement (null before).
    rating = fields.Nested(RatingSchema, allow_none=True)
    # A free engagement from the pro-bono queue (prices are 0).
    is_pro_bono = fields.Boolean(required=True)


class QuotePriceInputSchema(Schema):
    engagement_item_id = fields.UUID(required=True)
    price = _money(
        required=True,
        validate=validate.Range(min=0, max=MAX_PRICE, error="Enter a price from 0 to 10,00,000."),
    )


class QuoteInputSchema(Schema):
    """POST /marketplace/engagements/<id>/quote: a new price per filing and why."""

    reason = fields.String(required=True, validate=[validate.Length(1, 1000), _not_blank])
    prices = fields.List(
        fields.Nested(QuotePriceInputSchema),
        required=True,
        validate=validate.Length(min=1, error="Enter the new prices."),
    )


class RatingInputSchema(Schema):
    """POST /marketplace/engagements/<id>/rating: 1 to 5 stars and an optional review."""

    stars = fields.Integer(
        required=True, validate=validate.Range(1, 5, error="Choose 1 to 5 stars.")
    )
    review = fields.String(load_default="", validate=validate.Length(max=2000))


# --- Pro-bono queue (MA16) --------------------------------------------------------------


class ProBonoFilingSchema(Schema):
    id = fields.UUID(required=True)
    form_code = fields.String(validate=validate.OneOf(list(FormCode)), required=True)
    period_label = fields.String(required=True)
    due_date = fields.Date(required=True)
    # Why it cannot be chosen ("Already filed." ...); null when it can.
    blocked_reason = fields.String(allow_none=True)


class ProBonoRequestSchema(Schema):
    id = fields.UUID(required=True)
    status = fields.String(validate=validate.OneOf(list(ProBonoRequestStatus)), required=True)
    note = fields.String(required=True)
    created_at = fields.DateTime(required=True)
    business_name = fields.String(required=True)
    filings = fields.List(fields.Nested(ProBonoFilingSchema), required=True)


class ProBonoPageSchema(Schema):
    """GET /marketplace/pro-bono: what the business's pro-bono page shows."""

    eligible = fields.Boolean(required=True)
    reason = fields.String(required=True)
    request = fields.Nested(ProBonoRequestSchema, allow_none=True)  # its queued request
    filings = fields.List(fields.Nested(ProBonoFilingSchema), required=True)


class ProBonoJoinInputSchema(Schema):
    """POST /marketplace/pro-bono: the filings to get free help with, and a short note."""

    compliance_item_ids = fields.List(
        fields.UUID(),
        required=True,
        validate=validate.Length(min=1, error="Choose at least one filing."),
    )
    note = fields.String(load_default="", validate=validate.Length(max=1000))


class ProBonoQueueSchema(Schema):
    """GET /marketplace/pro-bono-queue: the CA's pledge, slots used this month, the queue."""

    pledged = fields.Integer(required=True)
    used_this_month = fields.Integer(required=True)
    verified = fields.Boolean(required=True)
    requests = fields.List(fields.Nested(ProBonoRequestSchema), required=True)
