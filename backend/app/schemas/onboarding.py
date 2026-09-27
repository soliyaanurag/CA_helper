"""Request and response shapes for /api/v1/onboarding/..."""

from decimal import Decimal

from marshmallow import (
    Schema,
    ValidationError,
    fields,
    post_load,
    pre_load,
    validate,
    validates_schema,
)

from app.models.onboarding import EntityType, GstScheme, ItrForm, MsmeTier

# Format checks only; checksums and cross-checks (GSTIN contains the PAN) come later (ON3).
PAN_FORMAT = r"^[A-Z]{5}[0-9]{4}[A-Z]$"  # e.g. ABCDE1234F
GSTIN_FORMAT = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$"  # e.g. 27ABCDE1234F1Z5
TAN_FORMAT = r"^[A-Z]{4}[0-9]{5}[A-Z]$"  # e.g. MUMA12345B
UDYAM_FORMAT = r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$"  # e.g. UDYAM-MH-01-0000001
PHONE_FORMAT = r"^[6-9][0-9]{9}$"  # 10-digit Indian mobile number

MAX_AMOUNT = Decimal("9999999999.99")  # the column holds Numeric(12, 2)

# Codes typed by people; stored in capitals without spaces around them.
CODE_FIELDS = ("pan", "gstin", "tan", "cin_llpin", "udyam_number")


def _text(max_length: int) -> fields.String:
    return fields.String(required=True, validate=validate.Length(1, max_length))


def _amount() -> fields.Decimal:
    return fields.Decimal(
        required=True, places=2, as_string=True, validate=validate.Range(0, MAX_AMOUNT)
    )


class BusinessInputSchema(Schema):
    """POST /onboarding/business: the registration form."""

    legal_name = _text(200)
    entity_type = fields.Enum(EntityType, by_value=True, required=True)
    state = _text(50)
    address = _text(500)
    description = _text(1000)
    annual_turnover = _amount()
    investment_amount = _amount()
    pan = fields.String(
        required=True, validate=validate.Regexp(PAN_FORMAT, error="Enter a valid PAN.")
    )
    phone = fields.String(
        required=True,
        validate=validate.Regexp(PHONE_FORMAT, error="Enter a 10-digit mobile number."),
    )
    gst_registered = fields.Boolean(required=True)
    gstin = fields.String(
        load_default=None, validate=validate.Regexp(GSTIN_FORMAT, error="Enter a valid GSTIN.")
    )
    gst_composition = fields.Boolean(load_default=False)
    deducts_tds = fields.Boolean(required=True)
    tan = fields.String(
        load_default=None, validate=validate.Regexp(TAN_FORMAT, error="Enter a valid TAN.")
    )
    pays_salary_above_limit = fields.Boolean(required=True)
    cin_llpin = fields.String(load_default=None, validate=validate.Length(1, 21))
    udyam_number = fields.String(
        load_default=None,
        validate=validate.Regexp(UDYAM_FORMAT, error="Enter a valid Udyam number."),
    )

    @pre_load
    def _clean_codes(self, data: dict, **kwargs) -> dict:
        """Trim and capitalise the codes; an empty code counts as not given."""
        data = dict(data)
        for key in CODE_FIELDS:
            value = data.get(key)
            if isinstance(value, str):
                data[key] = value.strip().upper() or None
        return data

    @validates_schema
    def _required_when(self, data: dict, **kwargs) -> None:
        """Fields that are required only for some businesses."""
        errors = {}
        if data.get("gst_registered") and not data.get("gstin"):
            errors["gstin"] = ["Enter your GSTIN (you said you are GST registered)."]
        if data.get("gst_composition") and not data.get("gst_registered"):
            errors["gst_composition"] = ["Only a GST-registered business can use composition."]
        if data.get("deducts_tds") and not data.get("tan"):
            errors["tan"] = ["Enter your TAN (you said you deduct TDS)."]
        if data.get("entity_type") in (EntityType.LLP, EntityType.PRIVATE_LIMITED) and not data.get(
            "cin_llpin"
        ):
            errors["cin_llpin"] = ["Enter your CIN (company) or LLPIN (LLP)."]
        if errors:
            raise ValidationError(errors)

    @post_load
    def _drop_unused(self, data: dict, **kwargs) -> dict:
        """Forget values that do not apply, e.g. a GSTIN sent with gst_registered = false."""
        if not data["gst_registered"]:
            data["gstin"] = None
        if not data["deducts_tds"]:
            data["tan"] = None
        if data["entity_type"] not in (EntityType.LLP, EntityType.PRIVATE_LIMITED):
            data["cin_llpin"] = None
        for key in ("legal_name", "state", "address", "description"):
            data[key] = data[key].strip()
        return data


class BusinessSchema(Schema):
    """The business as its owner sees it (all fields, decrypted)."""

    id = fields.UUID(required=True)
    legal_name = fields.String(required=True)
    entity_type = fields.Enum(EntityType, by_value=True, required=True)
    state = fields.String(required=True)
    address = fields.String(required=True)
    description = fields.String(required=True)
    annual_turnover = fields.Decimal(as_string=True, required=True)
    investment_amount = fields.Decimal(as_string=True, required=True)
    pan = fields.String(required=True)
    phone = fields.String(required=True)
    gst_registered = fields.Boolean(required=True)
    gstin = fields.String(allow_none=True)
    gst_composition = fields.Boolean(required=True)
    deducts_tds = fields.Boolean(required=True)
    tan = fields.String(allow_none=True)
    pays_salary_above_limit = fields.Boolean(required=True)
    cin_llpin = fields.String(allow_none=True)
    udyam_number = fields.String(allow_none=True)


class RegulatoryProfileSchema(Schema):
    """The computed profile; `explanations` has a "why" sentence for each line."""

    msme_tier = fields.Enum(MsmeTier, by_value=True, required=True)
    gst_scheme = fields.Enum(GstScheme, by_value=True, required=True)
    gst_registration_suggested = fields.Boolean(required=True)
    itr_form = fields.Enum(ItrForm, by_value=True, required=True)
    presumptive_eligible = fields.Boolean(required=True)
    audit_applicable = fields.Boolean(required=True)
    files_24q = fields.Boolean(required=True)
    files_26q = fields.Boolean(required=True)
    roc_not_tracked = fields.Boolean(required=True)
    explanations = fields.Dict(keys=fields.String(), values=fields.String(), required=True)
    rule_version = fields.String(required=True)
    computed_at = fields.DateTime(required=True)


class MyBusinessSchema(Schema):
    business = fields.Nested(BusinessSchema, required=True)
    profile = fields.Nested(RegulatoryProfileSchema, required=True)
