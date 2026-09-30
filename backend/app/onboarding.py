"""Request and response shapes for /api/v1/onboarding/...

Business logic for onboarding: registering a business and working out its regulatory profile.

register_business(user, data) -> dict     save the business, compute its profile, create its filings
update_business(business, data) -> dict   edit: recompute profile, sync filings, say what changed
get_my_business(business) -> dict         the business with its profile
list_states() -> list[dict]               the states / UTs for the form, with their GST codes
compute_profile(business, today) -> dict  the profile values plus a "why" for each (ON5, ON6)
get_business(business_id) -> Business     one business by id (used by marketplace)
get_msme_tier(business) -> str | None     "micro", "small", ... (used by marketplace pro-bono)
get_itr_form(business) -> str | None      its profile's ITR form, e.g. "itr_5" (used by marketplace)
business_ids_in_segment(entity, tier)     live businesses of one type and MSME tier (peer insights)
resync_all_filings(today) -> dict         every business's filings to the current rules (flask seed)
suggest_nic_codes(business) -> dict       up to 3 real NIC codes for its description (ON10)
search_nic_codes(query) -> list           manual search of the NIC list
set_nic_code(business, code) -> NicCode   save the code the user confirmed
read_registration_document(upload) -> dict  values read from a GST certificate / PAN card (ON13)

The profile is computed from legal thresholds stored in `rule_thresholds` (read
with _threshold()); no legal number is written in this file (CLAUDE.md rule 3).

Routes for onboarding (all under /api/v1).

    POST /api/v1/onboarding/business   business only   register the business (once)
    GET  /api/v1/onboarding/business   business only   the business with its regulatory profile
    PUT  /api/v1/onboarding/business   business only   edit it (profile recomputed, filings synced)
    GET  /api/v1/onboarding/states     business only   states / UTs with their GST codes
    POST /api/v1/onboarding/nic-suggestions  business only   up to 3 suggested NIC codes
    GET  /api/v1/onboarding/nic-codes?q=     business only   search the NIC list
    PUT  /api/v1/onboarding/business/nic-code  business only  save the confirmed NIC code
    POST /api/v1/onboarding/autofill   business only   read a GST certificate / PAN card (OCR)

Each route only checks who is calling, reads the input, calls one function in
app/onboarding.py and returns its result as JSON.
"""

import json
import logging
import re
from datetime import date
from decimal import Decimal

from flask_smorest import Blueprint
from marshmallow import (
    fields,
    post_load,
    pre_load,
    Schema,
    validate,
    validates_schema,
    ValidationError,
)
from sqlalchemy import func, or_, select

from app import compliance, ocr, utils
from app.models import (
    Business,
    db,
    EntityType,
    GstScheme,
    ItrForm,
    MsmeTier,
    NicCode,
    RegulatoryProfile,
    RuleThreshold,
    today_in_india,
    User,
    UserRole,
    utcnow,
)
from app.utils import (
    ApiError,
    current_business,
    current_user,
    ErrorSchema,
    format_inr,
    GST_STATES,
    gstin_error,
    roles_required,
    state_code,
)


# --- Request and response shapes ---------------------------------------------------------


# Format checks; the GSTIN's check character, state code and PAN are checked in
# _required_when() with app/utils/gstin.py.
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
    """POST and PUT /onboarding/business: the registration (and edit) form."""

    legal_name = _text(200)
    entity_type = fields.String(validate=validate.OneOf(list(EntityType)), required=True)
    state = fields.String(
        required=True,
        validate=validate.OneOf(
            [state["name"] for state in GST_STATES], error="Choose your state from the list."
        ),
    )
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
    # Regular scheme within the QRMP limit: quarterly returns (True) or monthly (False).
    gst_qrmp = fields.Boolean(load_default=False)
    # Partnerships and LLPs: are the accounts audited under another law?
    accounts_audited_other_law = fields.Boolean(load_default=False)
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
        # The fields' own checks passed (a bad value would be missing here).
        if data.get("gst_registered") and data.get("gstin") and state_code(data.get("state", "")):
            problem = gstin_error(data["gstin"], data.get("pan"), data["state"])
            if problem:
                errors["gstin"] = [problem]
        if errors:
            raise ValidationError(errors)

    @post_load
    def _drop_unused(self, data: dict, **kwargs) -> dict:
        """Forget values that do not apply, e.g. a GSTIN sent with gst_registered = false."""
        if not data["gst_registered"]:
            data["gstin"] = None
        if not data["deducts_tds"]:
            data["tan"] = None
        if not data["gst_registered"] or data["gst_composition"]:
            data["gst_qrmp"] = False
        if data["entity_type"] not in (EntityType.PARTNERSHIP, EntityType.LLP):
            data["accounts_audited_other_law"] = False
        if data["entity_type"] not in (EntityType.LLP, EntityType.PRIVATE_LIMITED):
            data["cin_llpin"] = None
        for key in ("legal_name", "address", "description"):
            data[key] = data[key].strip()
        return data


class BusinessSchema(Schema):
    """The business as its owner sees it (all fields, decrypted)."""

    id = fields.UUID(required=True)
    legal_name = fields.String(required=True)
    entity_type = fields.String(validate=validate.OneOf(list(EntityType)), required=True)
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
    gst_qrmp = fields.Boolean(required=True)
    accounts_audited_other_law = fields.Boolean(required=True)
    deducts_tds = fields.Boolean(required=True)
    tan = fields.String(allow_none=True)
    pays_salary_above_limit = fields.Boolean(required=True)
    cin_llpin = fields.String(allow_none=True)
    udyam_number = fields.String(allow_none=True)
    # True when the saved state is not in the state list (typed before the list existed):
    # the form asks the user to choose it again.
    state_needs_review = fields.Function(lambda business: state_code(business.state) is None)


class RegulatoryProfileSchema(Schema):
    """The computed profile; `explanations` has a "why" sentence for each line."""

    msme_tier = fields.String(validate=validate.OneOf(list(MsmeTier)), required=True)
    gst_scheme = fields.String(validate=validate.OneOf(list(GstScheme)), required=True)
    gst_registration_suggested = fields.Boolean(required=True)
    itr_form = fields.String(validate=validate.OneOf(list(ItrForm)), required=True)
    presumptive_eligible = fields.Boolean(required=True)
    audit_applicable = fields.Boolean(required=True)
    other_audit_applicable = fields.Boolean(required=True)
    files_24q = fields.Boolean(required=True)
    files_26q = fields.Boolean(required=True)
    roc_not_tracked = fields.Boolean(required=True)
    explanations = fields.Dict(keys=fields.String(), values=fields.String(), required=True)
    rule_version = fields.String(required=True)
    computed_at = fields.DateTime(required=True)


class NicCodeSchema(Schema):
    """One official NIC activity code, e.g. 10712 "Manufacture of biscuits, cakes, ..."."""

    code = fields.String(required=True)
    description = fields.String(required=True)


class MyBusinessSchema(Schema):
    business = fields.Nested(BusinessSchema, required=True)
    profile = fields.Nested(RegulatoryProfileSchema, required=True)
    # The NIC code the user confirmed; null until they choose one.
    nic_code = fields.Nested(NicCodeSchema, allow_none=True)


class ProfileChangeSchema(Schema):
    """One profile line that changed: its code before and after (e.g. "regular_monthly")."""

    line = fields.String(required=True)
    old = fields.Raw(required=True)
    new = fields.Raw(required=True)


class FilingChangesSchema(Schema):
    added = fields.Integer(required=True)
    restored = fields.Integer(required=True)
    removed = fields.Integer(required=True)
    moved = fields.Integer(required=True)
    kept_with_ca = fields.Integer(required=True)


class BusinessChangesSchema(Schema):
    profile = fields.List(fields.Nested(ProfileChangeSchema), required=True)
    filings = fields.Nested(FilingChangesSchema, required=True)


class MyBusinessUpdateSchema(MyBusinessSchema):
    """PUT /onboarding/business: the saved business and profile, and what changed."""

    changes = fields.Nested(BusinessChangesSchema, required=True)


class NicPickSchema(NicCodeSchema):
    """One suggested code with its reason; source "ai" (Gemini's pick) or "keywords"."""

    reason = fields.String(required=True)
    source = fields.String(required=True)


class NicSuggestionSchema(Schema):
    """POST /onboarding/nic-suggestions: up to 3 picks, the keyword shortlist they came from."""

    picks = fields.List(fields.Nested(NicPickSchema), required=True)
    shortlist = fields.List(fields.Nested(NicCodeSchema), required=True)
    ai_used = fields.Boolean(required=True)


class NicSearchQuerySchema(Schema):
    q = fields.String(load_default="", validate=validate.Length(max=100))


class NicCodeInputSchema(Schema):
    """PUT /onboarding/business/nic-code: the code the user confirmed."""

    code = fields.String(required=True, validate=validate.Length(1, 10))


class GstStateSchema(Schema):
    name = fields.String(required=True)
    code = fields.String(required=True)  # the first two digits of a GSTIN from this state


class RegistrationUploadSchema(Schema):
    """POST /onboarding/autofill (multipart/form-data): a GST certificate or PAN card."""

    file = fields.Raw(required=True, metadata={"type": "string", "format": "binary"})


class RegistrationFieldsSchema(Schema):
    pan = fields.String()
    gstin = fields.String()
    legal_name = fields.String()
    state = fields.String()
    entity_type = fields.String(validate=validate.OneOf(list(EntityType)))


class AutofillSchema(Schema):
    """What the document showed; only the fields that were found."""

    found = fields.Nested(RegistrationFieldsSchema, required=True)


# --- Logic -------------------------------------------------------------------------------


log = logging.getLogger(__name__)

# Which version of the profile logic below produced a profile. Change it when the logic changes.
RULE_VERSION = "v2"  # v2: QRMP is the user's choice; the audit line is split in two


def _threshold(key: str, today: date) -> Decimal:
    """The legal value `key` in force today, from the rule_thresholds table."""
    row = db.session.scalar(
        select(RuleThreshold)
        .where(
            RuleThreshold.key == key,
            RuleThreshold.effective_from <= today,
            or_(RuleThreshold.effective_to.is_(None), RuleThreshold.effective_to > today),
        )
        .order_by(RuleThreshold.effective_from.desc())
    )
    if row is None:
        raise ApiError(500, "RULE_MISSING", f"The rule '{key}' is missing. Run `make seed`.")
    return row.value


def _rupees(amount: Decimal) -> str:
    """An amount for the "why" texts in the Indian format, e.g. ₹2,00,00,000."""
    return format_inr(amount)


def compute_profile(business: Business, today: date) -> dict:
    """Work out the regulatory profile of `business`, with a "why" for every line.

    Returns the values of a RegulatoryProfile row (without business_id and computed_at).
    """
    turnover = business.annual_turnover
    investment = business.investment_amount
    entity = business.entity_type
    why = {}

    # 1. MSME tier: the smallest tier whose investment AND turnover limits both fit.
    msme_tier = MsmeTier.NOT_MSME
    why["msme_tier"] = "Investment or turnover is above the medium-enterprise limits."
    for tier in (MsmeTier.MICRO, MsmeTier.SMALL, MsmeTier.MEDIUM):
        max_investment = _threshold(f"msme.{tier}.max_investment", today)
        max_turnover = _threshold(f"msme.{tier}.max_turnover", today)
        if investment <= max_investment and turnover <= max_turnover:
            msme_tier = tier
            why["msme_tier"] = (
                f"Investment {_rupees(investment)} is within {_rupees(max_investment)} and "
                f"turnover {_rupees(turnover)} is within {_rupees(max_turnover)}."
            )
            break

    # 2. GST scheme.
    registration_limit = _threshold("gst.registration.min_turnover", today)
    composition_limit = _threshold("gst.composition.max_turnover", today)
    qrmp_limit = _threshold("gst.qrmp.max_turnover", today)
    gst_registration_suggested = False
    if not business.gst_registered:
        gst_scheme = GstScheme.NOT_REGISTERED
        if turnover > registration_limit:
            gst_registration_suggested = True
            why["gst_scheme"] = (
                f"Not registered, but turnover is above {_rupees(registration_limit)}: "
                "you may need GST registration. Ask a CA."
            )
        else:
            why["gst_scheme"] = f"Not registered; turnover is within {_rupees(registration_limit)}."
    elif business.gst_composition and turnover <= composition_limit:
        gst_scheme = GstScheme.COMPOSITION
        why["gst_scheme"] = (
            f"You chose the composition scheme and turnover is within {_rupees(composition_limit)}."
        )
    else:
        note = ""
        if business.gst_composition:
            note = f"Composition is not allowed above {_rupees(composition_limit)}. "
        if turnover > qrmp_limit:
            gst_scheme = GstScheme.REGULAR_MONTHLY
            why["gst_scheme"] = (
                f"{note}Turnover is above {_rupees(qrmp_limit)}, so returns are monthly "
                "(quarterly QRMP is not allowed)."
            )
        elif business.gst_qrmp:
            gst_scheme = GstScheme.REGULAR_QRMP
            why["gst_scheme"] = (
                f"{note}You chose quarterly returns (QRMP), allowed because turnover is within "
                f"{_rupees(qrmp_limit)}."
            )
        else:
            gst_scheme = GstScheme.REGULAR_MONTHLY
            why["gst_scheme"] = (
                f"{note}You chose monthly returns. Quarterly (QRMP) is also allowed within "
                f"{_rupees(qrmp_limit)}."
            )

    # 3. Presumptive scheme (section 44AD; section 58 of the 2025 Act): individuals, proprietors
    #    and partnership firms.
    presumptive_limit = _threshold("itr.presumptive_44ad.max_turnover", today)
    if entity in (EntityType.LLP, EntityType.PRIVATE_LIMITED):
        presumptive_eligible = False
        why["presumptive_eligible"] = "LLPs and companies cannot use the presumptive scheme."
    elif turnover <= presumptive_limit:
        presumptive_eligible = True
        why["presumptive_eligible"] = f"Turnover is within {_rupees(presumptive_limit)}."
    else:
        presumptive_eligible = False
        why["presumptive_eligible"] = f"Turnover is above {_rupees(presumptive_limit)}."

    # 4. Audits (either one moves the ITR due date later).
    # 4a. Tax audit under section 44AB (section 63 of the 2025 Act), from turnover.
    audit_limit = _threshold("itr.audit_44ab.min_turnover", today)
    if presumptive_eligible:
        audit_applicable = False
        why["audit_applicable"] = "No tax audit when you use the presumptive scheme."
    elif turnover > audit_limit:
        audit_applicable = True
        why["audit_applicable"] = f"Turnover is above {_rupees(audit_limit)}."
    else:
        audit_applicable = False
        why["audit_applicable"] = f"Turnover is within {_rupees(audit_limit)}."

    # 4b. Accounts audited under another law: companies always; partnerships and LLPs
    # answer the question on the form (whether it applies depends on their own rules).
    if entity == EntityType.PRIVATE_LIMITED:
        other_audit_applicable = True
        why["other_audit_applicable"] = "A company's accounts are always audited (company law)."
    elif entity in (EntityType.PARTNERSHIP, EntityType.LLP):
        other_audit_applicable = business.accounts_audited_other_law
        why["other_audit_applicable"] = (
            "You said your accounts are audited under another law."
            if other_audit_applicable
            else "You said your accounts are not audited under another law."
        )
    else:
        other_audit_applicable = False
        why["other_audit_applicable"] = "Individuals and proprietors: only the tax audit applies."

    # 5. ITR form.
    if entity == EntityType.PRIVATE_LIMITED:
        itr_form = ItrForm.ITR_6
        why["itr_form"] = "Companies file ITR-6."
    elif entity == EntityType.LLP:
        itr_form = ItrForm.ITR_5
        why["itr_form"] = "LLPs file ITR-5."
    elif presumptive_eligible:
        itr_form = ItrForm.ITR_4
        why["itr_form"] = "Presumptive income is filed in ITR-4."
    elif entity == EntityType.PARTNERSHIP:
        itr_form = ItrForm.ITR_5
        why["itr_form"] = "Partnership firms outside the presumptive scheme file ITR-5."
    else:
        itr_form = ItrForm.ITR_3
        why["itr_form"] = "Business or professional income outside the presumptive scheme: ITR-3."

    # 6. TDS returns.
    files_26q = business.deducts_tds
    files_24q = business.deducts_tds and business.pays_salary_above_limit
    why["files_24q"] = (
        "You deduct TDS on salaries." if files_24q else "You do not deduct TDS on salaries."
    )
    why["files_26q"] = (
        "You deduct TDS on other payments." if files_26q else "You do not deduct TDS."
    )

    # 7. ROC/MCA filings are out of scope; LLPs and companies get a notice.
    roc_not_tracked = entity in (EntityType.LLP, EntityType.PRIVATE_LIMITED)
    why["roc_not_tracked"] = (
        "LLPs and companies also have ROC/MCA filings, which this app does not track."
        if roc_not_tracked
        else "No ROC/MCA filings for this business type."
    )

    return {
        "msme_tier": msme_tier,
        "gst_scheme": gst_scheme,
        "gst_registration_suggested": gst_registration_suggested,
        "itr_form": itr_form,
        "presumptive_eligible": presumptive_eligible,
        "audit_applicable": audit_applicable,
        "other_audit_applicable": other_audit_applicable,
        "files_24q": files_24q,
        "files_26q": files_26q,
        "roc_not_tracked": roc_not_tracked,
        "explanations": why,
        "rule_version": RULE_VERSION,
    }


def register_business(user: User, data: dict) -> dict:
    """Save the user's business, compute its profile and create its filings (one commit).

    409 BUSINESS_EXISTS if the user already registered one (one business per user).
    """
    exists = db.session.scalar(
        select(Business.id).where(Business.user_id == user.id)
    )
    if exists:
        raise ApiError(409, "BUSINESS_EXISTS", "You have already registered your business.")

    business = Business(user_id=user.id, **data)
    db.session.add(business)
    db.session.flush()  # gives business.id

    today = today_in_india()
    profile = RegulatoryProfile(
        business_id=business.id, computed_at=utcnow(), **compute_profile(business, today)
    )
    db.session.add(profile)
    added = compliance.create_filings(business.id, profile, today)

    db.session.commit()
    log.info("Business %s registered with %d filings", business.id, added)
    return {"business": business, "profile": profile, "nic_code": None}


# The profile lines compared in the "What changed" summary after an edit.
COMPARED_LINES = (
    "msme_tier",
    "gst_scheme",
    "itr_form",
    "presumptive_eligible",
    "audit_applicable",
    "other_audit_applicable",
    "files_24q",
    "files_26q",
)


def _code(value):
    """An enum's code, or the value itself (True / False)."""
    return getattr(value, "value", value)


def update_business(business: Business, data: dict) -> dict:
    """Save the edited form, recompute the profile in place and sync this year's filings
    (one commit). Returns the business, the profile and what changed:
    {"profile": [{"line", "old", "new"}], "filings": {added, restored, removed, moved,
    kept_with_ca}}. Filings in an open CA engagement are never removed.
    """
    # Imported here: marketplace imports this module (a top-level import would loop).
    from app import marketplace

    for field, value in data.items():
        setattr(business, field, value)

    today = today_in_india()
    profile = db.session.scalar(
        select(RegulatoryProfile).where(RegulatoryProfile.business_id == business.id)
    )
    old = {line: _code(getattr(profile, line)) for line in COMPARED_LINES}
    for field, value in compute_profile(business, today).items():
        setattr(profile, field, value)
    profile.computed_at = utcnow()

    filing_ids = [filing.id for filing in compliance.list_filings(business)]
    keep = marketplace.open_filing_ids(filing_ids)
    filings = compliance.sync_filings(business.id, profile, today, keep)
    db.session.commit()

    changed = []
    for line in COMPARED_LINES:
        new = _code(getattr(profile, line))
        if new != old[line]:
            changed.append({"line": line, "old": old[line], "new": new})
    log.info("Business %s updated: %d profile lines changed", business.id, len(changed))
    return {
        "business": business,
        "profile": profile,
        "nic_code": _nic_code_of(business),
        "changes": {"profile": changed, "filings": filings},
    }


def list_states() -> list[dict]:
    """The states and union territories with their GST codes (reference data)."""
    return GST_STATES


def get_my_business(business: Business) -> dict:
    """The business together with its regulatory profile and its NIC code (or None)."""
    profile = db.session.scalar(
        select(RegulatoryProfile).where(RegulatoryProfile.business_id == business.id)
    )
    return {"business": business, "profile": profile, "nic_code": _nic_code_of(business)}


def _nic_code_of(business: Business) -> NicCode | None:
    """The business's confirmed NIC code row, or None if it has not chosen one."""
    if business.nic_code_id is None:
        return None
    return db.session.get(NicCode, business.nic_code_id)


# ---------------------------------------------------------------------------
# NIC activity code (ON9 list, ON10 suggestion)
#
# 1. Keyword shortlist: the codes whose description contains the most words of the
#    business's own description (real codes only, from the nic_codes table).
# 2. Gemini picks the best 3 from that shortlist and says why. A code that is not in
#    the shortlist is thrown away, so Gemini can never invent a code.
# 3. Fewer than 3 good picks (or no Gemini): the top keyword matches fill the gap.
# 4. The user confirms one code (set_nic_code); nothing is saved before that.
# ---------------------------------------------------------------------------

NIC_SHORTLIST_SIZE = 15
NIC_PICKS = 3

# Words that say nothing about the activity; they are not used for matching.
COMMON_WORDS = {
    "and",
    "the",
    "for",
    "with",
    "our",
    "are",
    "from",
    "all",
    "any",
    "also",
    "into",
    "its",
    "this",
    "that",
    "who",
    "we",
    "you",
    "your",
    "they",
    "them",
    "their",
    "have",
    "has",
    "business",
    "company",
    "firm",
    "services",
    "service",
    "work",
    "working",
    "provide",
    "providing",
    "products",
    "product",
    "sell",
    "selling",
    "sale",
    "sales",
    "other",
    "etc",
    "like",
    "such",
    "small",
    "local",
    "customers",
    "people",
    "since",
    "year",
    "years",
    "based",
    "various",
    "different",
    "good",
    "quality",
    "india",
    "own",
    "near",
    "doing",
    "done",
    "make",
    "making",
    "made",
}


def _match_words(description: str) -> list[str]:
    """The useful words of a description, lowercase, without a plural "s".

    Personal data (emails, phone numbers, ...) is removed first: it says nothing
    about the activity and "com" from an email would match "computer".
    """
    words = []
    clean, _ = utils.scrub_pii(description)
    text = re.sub(r"\[[a-z]+\]", " ", clean.lower())  # the [EMAIL]-style placeholders
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    for word in text.split():
        if len(word) < 3 or word in COMMON_WORDS:
            continue
        if len(word) > 4 and word.endswith("s"):
            word = word[:-1]  # "biscuits" also matches "biscuit"
        if word not in words:
            words.append(word)
    return words


def shortlist_nic_codes(description: str, limit: int = NIC_SHORTLIST_SIZE) -> list[NicCode]:
    """The codes whose description best matches the words of `description`, best first.

    A word found in few codes says more than a common one ("tea" is in 4 codes,
    "station" in many), so each matching word adds 1 / (number of codes containing it).
    """
    words = _match_words(description)
    if not words:
        return []

    # 1. Which codes contain which words.
    all_codes = list(db.session.scalars(select(NicCode).order_by(NicCode.code)))
    found_in = {}  # word -> how many codes contain it
    matched = []  # (code, [its matching words])
    for word in words:
        found_in[word] = 0
    for nic in all_codes:
        nic_text = nic.description.lower()
        nic_words = []
        for word in words:
            if _word_in(word, nic_text):
                nic_words.append(word)
                found_in[word] += 1
        if nic_words:
            matched.append((nic, nic_words))

    # 2. Score: rarer words count more.
    scored = []
    for nic, nic_words in matched:
        score = 0.0
        for word in nic_words:
            score += 1 / found_in[word]
        scored.append((score, nic))

    # Highest score first; equal scores keep code order (the sort is stable).
    scored.sort(key=_score_of, reverse=True)
    shortlist = []
    for _, nic in scored[:limit]:
        shortlist.append(nic)
    return shortlist


def _word_in(word: str, text: str) -> bool:
    """Does `text` contain `word`? Longer words also match as the start of a word
    ("bake" matches "bakery"); 3-letter words only as a whole word ("tea", not "steam")."""
    if len(word) <= 3:
        return re.search(r"\b" + re.escape(word) + r"s?\b", text) is not None
    return re.search(r"\b" + re.escape(word), text) is not None


def _score_of(pair: tuple) -> float:
    return pair[0]


def _nic_prompt(description: str, shortlist: list[NicCode]) -> str:
    """The question for Gemini: the description and the shortlist, nothing else."""
    lines = []
    for nic in shortlist:
        lines.append(f"{nic.code}: {nic.description}")
    return (
        "You help an Indian small business choose its NIC-2008 activity code.\n"
        f"Business description: {description}\n\n"
        "Choose the 3 codes from this list that best fit the business, best first:\n"
        + "\n".join(lines)
        + "\n\nUse only codes from the list. For each, give a one-sentence reason.\n"
        'Reply with JSON only: {"picks": [{"code": "...", "reason": "..."}]}'
    )


def _ai_picks(reply: str, shortlist: list[NicCode]) -> list[dict]:
    """The valid picks in Gemini's reply: codes from the shortlist only, no repeats, at most 3."""
    try:
        data = json.loads(reply)
    except ValueError:
        log.warning("Gemini's NIC reply was not JSON")
        return []
    if not isinstance(data, dict) or not isinstance(data.get("picks"), list):
        return []

    allowed = {}
    for nic in shortlist:
        allowed[nic.code] = nic
    picks = []
    for item in data["picks"]:
        if len(picks) == NIC_PICKS:
            break
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip()
        if code not in allowed or _already_picked(picks, code):
            continue  # an invented or repeated code is dropped
        reason = str(item.get("reason", "")).strip()[:300]
        picks.append(_pick(allowed[code], reason or "Suggested by AI.", "ai"))
    return picks


def _already_picked(picks: list[dict], code: str) -> bool:
    found = False
    for pick in picks:
        if pick["code"] == code:
            found = True
    return found


def _pick(nic: NicCode, reason: str, source: str) -> dict:
    return {"code": nic.code, "description": nic.description, "reason": reason, "source": source}


def suggest_nic_codes(business: Business) -> dict:
    """Up to 3 suggested NIC codes for the business (nothing is saved).

    Returns {"picks": [{code, description, reason, source: "ai" | "keywords"}],
    "shortlist": [{code, description}], "ai_used": bool}.
    """
    shortlist = shortlist_nic_codes(business.description)

    picks = []
    if shortlist and utils.gemini_available():
        try:
            reply = utils.ask_gemini(
                _nic_prompt(business.description, shortlist), want_json=True
            )
            picks = _ai_picks(reply, shortlist)
        except ApiError:
            log.info("Gemini unavailable; NIC suggestions use keyword matches only")
    ai_used = len(picks) > 0

    # Fill up to 3 with the best keyword matches not picked yet.
    for nic in shortlist:
        if len(picks) == NIC_PICKS:
            break
        if not _already_picked(picks, nic.code):
            picks.append(_pick(nic, "Matches words in your description.", "keywords"))

    return {"picks": picks, "shortlist": shortlist, "ai_used": ai_used}


def search_nic_codes(query: str) -> list[NicCode]:
    """Up to 20 codes whose code or description contains `query` (manual choice)."""
    query = query.strip()
    if len(query) < 2:
        return []
    pattern = f"%{query}%"
    stmt = (
        select(NicCode)
        .where(or_(NicCode.code.ilike(pattern), NicCode.description.ilike(pattern)))
        .order_by(NicCode.code)
        .limit(20)
    )
    return list(db.session.scalars(stmt))


def set_nic_code(business: Business, code: str) -> NicCode:
    """Save the NIC code the user confirmed. 422 UNKNOWN_NIC_CODE if it is not in the list."""
    nic = db.session.scalar(select(NicCode).where(NicCode.code == code.strip()))
    if nic is None:
        raise ApiError(422, "UNKNOWN_NIC_CODE", "Choose a code from the NIC list.")
    business.nic_code_id = nic.id
    db.session.commit()
    log.info("Business %s chose NIC code %s", business.id, nic.code)
    return nic


def get_business(business_id) -> Business | None:
    """One business by id (used by the marketplace module to show its name)."""
    return db.session.get(Business, business_id)


def get_itr_form(business: Business) -> str | None:
    """The ITR form of the business's regulatory profile, e.g. "itr_5" (None without a profile)."""
    profile = db.session.scalar(
        select(RegulatoryProfile).where(RegulatoryProfile.business_id == business.id)
    )
    if profile is None:
        return None
    return profile.itr_form


def count_businesses() -> int:
    """How many businesses are registered (admin dashboard)."""
    return db.session.scalar(select(func.count(Business.id)))


def business_of_user(user: User) -> Business | None:
    """The user's live business, or None before registration (used by marketplace)."""
    return db.session.scalar(
        select(Business).where(Business.user_id == user.id)
    )


def get_msme_tier(business: Business) -> str | None:
    """The MSME tier of the business's regulatory profile, e.g. "micro" (None without a profile)."""
    profile = db.session.scalar(
        select(RegulatoryProfile).where(RegulatoryProfile.business_id == business.id)
    )
    if profile is None:
        return None
    return profile.msme_tier


def business_categories(business_ids) -> list[dict]:
    """For live businesses among `business_ids`: {id, user_id, legal_name, entity_type,
    state, gst_scheme} (category-level facts only; used to match regulatory changes)."""
    stmt = (
        select(Business, RegulatoryProfile.gst_scheme)
        .join(RegulatoryProfile, RegulatoryProfile.business_id == Business.id)
        .where(Business.id.in_(list(business_ids)))
        .order_by(Business.legal_name)
    )
    rows = []
    for business, gst_scheme in db.session.execute(stmt):
        rows.append(
            {
                "id": business.id,
                "user_id": business.user_id,
                "legal_name": business.legal_name,
                "entity_type": business.entity_type,
                "state": business.state,
                "gst_scheme": gst_scheme,
            }
        )
    return rows


def business_ids_in_segment(entity_type, msme_tier) -> set:
    """The live businesses with this entity type and MSME tier (peer insights, CO13)."""
    stmt = (
        select(Business.id)
        .join(RegulatoryProfile, RegulatoryProfile.business_id == Business.id)
        .where(
            Business.entity_type == entity_type,
            RegulatoryProfile.msme_tier == msme_tier,
        )
    )
    return set(db.session.scalars(stmt))


# ---------------------------------------------------------------------------
# OCR auto-fill (ON13)
# ---------------------------------------------------------------------------


def read_registration_document(upload) -> dict:
    """Read a GST registration certificate or PAN card locally and suggest form values.

    Returns {"found": {pan?, gstin?, legal_name?, state?, entity_type?}}. The file is read
    in memory and thrown away: nothing is stored and nothing is saved to the business;
    the user checks the values in the form first (CLAUDE.md rules 2 and 4).
    Storage checks: 400 FILE_EMPTY, FILE_TYPE_NOT_ALLOWED, FILE_TOO_LARGE.
    422 DOCUMENT_UNREADABLE when no text could be read.
    """
    data = upload.read()
    utils.check_file(data, upload.mimetype)
    try:
        text = ocr.extract_text(data, upload.mimetype)
    except ocr.OcrError as error:
        raise ApiError(
            422, "DOCUMENT_UNREADABLE", f"We could not read this file. {error}"
        ) from error
    found = ocr.read_registration(text)
    if "entity_type" in found:
        found["entity_type"] = EntityType(found["entity_type"])
    log.info("Auto-fill read %d field(s) from a document", len(found))
    return {"found": found}


def resync_all_filings(today: date | None = None) -> dict:
    """Match every live business's filings of this financial year to the current obligation
    templates (sync_filings with its saved profile), so a corrected due-date rule reaches
    filings created earlier: not-started filings get the new date; filed, "With CA" and
    requested ones are kept. Does not commit (run by `flask seed`). Returns the summed counts.
    """
    from app import marketplace  # imported here: it imports this module

    today = today or today_in_india()
    totals = {"businesses": 0, "added": 0, "restored": 0, "removed": 0, "moved": 0}
    stmt = (
        select(Business, RegulatoryProfile)
        .join(RegulatoryProfile, RegulatoryProfile.business_id == Business.id)
    )
    for business, profile in db.session.execute(stmt).all():
        filing_ids = [filing.id for filing in compliance.list_filings(business)]
        keep = marketplace.open_filing_ids(filing_ids)
        counts = compliance.sync_filings(business.id, profile, today, keep)
        totals["businesses"] += 1
        for key in ("added", "restored", "removed", "moved"):
            totals[key] += counts[key]
    if totals["moved"] or totals["added"] or totals["removed"]:
        log.info("Filings resynced to the rules: %s", totals)
    return totals


# --- Routes ------------------------------------------------------------------------------


blp = Blueprint("onboarding", __name__, description="Business registration and regulatory profile")


# A business user registers their business. This also computes the regulatory
# profile and creates the filings of the current financial year.
@blp.route("/onboarding/business", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(BusinessInputSchema)
@blp.response(201, MyBusinessSchema)
@blp.alt_response(409, schema=ErrorSchema, description="BUSINESS_EXISTS (already registered)")
def register_business_view(data):
    return register_business(current_user(), data)


# The business user reads their business and its profile (with a "why" per line).
@blp.route("/onboarding/business", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, MyBusinessSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND (register first)")
def get_my_business_view():
    return get_my_business(current_business())


# The business user edits their business: the profile is recomputed and this year's
# filings follow it; the answer says what changed.
@blp.route("/onboarding/business", methods=["PUT"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(BusinessInputSchema)
@blp.response(200, MyBusinessUpdateSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND (register first)")
def update_my_business(data):
    return update_business(current_business(), data)


# Suggest up to 3 NIC activity codes for the business's description (nothing is saved).
# Limited per minute because each call can use the Gemini quota.
@blp.route("/onboarding/nic-suggestions", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, NicSuggestionSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND (register first)")
def suggest_nic_codes_view():
    return suggest_nic_codes(current_business())


# Search the official NIC list by code or words, for choosing a code by hand.
@blp.route("/onboarding/nic-codes", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(NicSearchQuerySchema, location="query")
@blp.response(200, NicCodeSchema(many=True))
def search_nic_codes_view(args):
    return search_nic_codes(args["q"])


# Save the NIC code the user confirmed.
@blp.route("/onboarding/business/nic-code", methods=["PUT"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(NicCodeInputSchema)
@blp.response(200, NicCodeSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND (register first)")
@blp.alt_response(422, schema=ErrorSchema, description="UNKNOWN_NIC_CODE (not in the list)")
def set_nic_code_view(data):
    return set_nic_code(current_business(), data["code"])


# The states and union territories for the form's dropdown.
@blp.route("/onboarding/states", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, GstStateSchema(many=True))
def list_states_view():
    return list_states()


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
    return read_registration_document(files["file"])
