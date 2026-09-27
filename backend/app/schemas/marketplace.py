"""Request and response shapes for /api/v1/marketplace/..."""

from marshmallow import Schema, ValidationError, fields, post_load, validate

from app.models.marketplace import (
    CA_LANGUAGES,
    CA_SPECIALIZATIONS,
    CaVerificationStatus,
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

    @post_load
    def _clean(self, data: dict, **kwargs) -> dict:
        """Trim text; store each code once, in a fixed order."""
        for key in ("cop_number", "city", "about"):
            data[key] = data[key].strip()
        data["languages"] = [code for code in CA_LANGUAGES if code in data["languages"]]
        data["specializations"] = [
            code for code in CA_SPECIALIZATIONS if code in data["specializations"]
        ]
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
    verification_status = fields.Enum(CaVerificationStatus, by_value=True, required=True)
    updated_at = fields.DateTime(required=True)


class CaListArgsSchema(PageArgsSchema):
    """GET /marketplace/cas filters; all optional."""

    specialization = fields.String(validate=validate.OneOf(CA_SPECIALIZATIONS))
    language = fields.String(validate=validate.OneOf(CA_LANGUAGES))
    city = fields.String(validate=validate.Length(max=100))
    # A catalog service code, e.g. "gstr_3b": only CAs who offer it, with their price.
    service = fields.String(validate=validate.Length(max=50))


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
    unit = fields.Enum(ServiceUnit, by_value=True, required=True)
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
