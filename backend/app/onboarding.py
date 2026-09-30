"""Registering a business, its regulatory profile (with a "why" for every line), the NIC
activity code and reading a registration document to fill the form.

The profile is computed from legal thresholds stored in `rule_thresholds`; no legal
number is written in this file.
"""

import json
import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, select

from app import compliance, ocr, utils
from app.models import (
    Business,
    EntityType,
    GstScheme,
    ItrForm,
    MsmeTier,
    NicCode,
    RegulatoryProfile,
    RuleThreshold,
    User,
    UserRole,
    db,
    today_in_india,
    utcnow,
)
from app.utils import (
    GST_STATES,
    MISSING,
    ApiError,
    current_business,
    current_user,
    format_inr,
    gstin_error,
    iso,
    json_body,
    money,
    roles_required,
    state_code,
    validation_error,
)

log = logging.getLogger(__name__)

bp = Blueprint("onboarding", __name__)

# Which version of the profile logic below produced a profile. Change it when the logic changes.
RULE_VERSION = "v2"  # v2: QRMP is the user's choice; the audit line is split in two

PAN_FORMAT = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")  # e.g. ABCDE1234F
GSTIN_FORMAT = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")  # 27ABCDE1234F1Z5
TAN_FORMAT = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")  # e.g. MUMA12345B
UDYAM_FORMAT = re.compile(r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$")  # e.g. UDYAM-MH-01-0000001
PHONE_FORMAT = re.compile(r"^[6-9][0-9]{9}$")  # 10-digit Indian mobile number
MAX_AMOUNT = Decimal("9999999999.99")  # the column holds Numeric(12, 2)

# Text fields of the form and their longest length.
TEXT_FIELDS = {"legal_name": 200, "address": 500, "description": 1000}
# Yes/no questions every business answers, and those that default to "no".
REQUIRED_FLAGS = ("gst_registered", "deducts_tds", "pays_salary_above_limit")
OPTIONAL_FLAGS = ("gst_composition", "gst_qrmp", "accounts_audited_other_law")
# Codes typed by people: stored in capitals, and an empty code counts as not given.
CODE_FIELDS = ("pan", "gstin", "tan", "cin_llpin", "udyam_number")
COMPANY_TYPES = (EntityType.LLP, EntityType.PRIVATE_LIMITED)

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


# --- The registration form ---------------------------------------------------------------


def read_business_form(data: dict) -> dict:
    """Check the registration (and edit) form and return the values to save.

    Raises 422 VALIDATION_ERROR naming every wrong field. The checks that depend on other
    answers (a GSTIN when GST registered, ...) run once every field is valid on its own.
    """
    errors = {}
    values = {}
    for field, max_length in TEXT_FIELDS.items():
        text = data.get(field)
        if text is None:
            errors[field] = [MISSING]
        elif not isinstance(text, str) or not 1 <= len(text) <= max_length:
            errors[field] = [f"Length must be between 1 and {max_length}."]
        else:
            values[field] = text.strip()

    entity_type = data.get("entity_type")
    if entity_type is None:
        errors["entity_type"] = [MISSING]
    elif entity_type not in list(EntityType):
        errors["entity_type"] = [f"Must be one of: {', '.join(EntityType)}."]
    values["entity_type"] = entity_type

    state = data.get("state")
    if state is None:
        errors["state"] = [MISSING]
    elif not isinstance(state, str) or state_code(state) is None:
        errors["state"] = ["Choose your state from the list."]
    values["state"] = state

    for field in ("annual_turnover", "investment_amount"):
        amount = data.get(field)
        if amount is None:
            errors[field] = [MISSING]
            continue
        try:
            if isinstance(amount, bool):
                raise InvalidOperation
            amount = Decimal(str(amount)).quantize(Decimal("0.01"))
        except InvalidOperation:
            errors[field] = ["Not a valid number."]
            continue
        if not 0 <= amount <= MAX_AMOUNT:
            errors[field] = [
                f"Must be greater than or equal to 0 and less than or equal to {MAX_AMOUNT}."
            ]
        values[field] = amount

    for field in REQUIRED_FLAGS + OPTIONAL_FLAGS:
        flag = data.get(field)
        if flag is None:
            if field in REQUIRED_FLAGS:
                errors[field] = [MISSING]
            values[field] = False
        elif not isinstance(flag, bool):
            errors[field] = ["Not a valid boolean."]
        else:
            values[field] = flag

    for field in CODE_FIELDS:
        code = data.get(field)
        if isinstance(code, str):
            code = code.strip().upper() or None
        values[field] = code
    formats = [
        ("pan", PAN_FORMAT, "Enter a valid PAN."),
        ("gstin", GSTIN_FORMAT, "Enter a valid GSTIN."),
        ("tan", TAN_FORMAT, "Enter a valid TAN."),
        ("udyam_number", UDYAM_FORMAT, "Enter a valid Udyam number."),
    ]
    for field, pattern, message in formats:
        code = values[field]
        if code is not None and (not isinstance(code, str) or not pattern.match(code)):
            errors[field] = [message]
    if values["pan"] is None:
        errors["pan"] = ["Field may not be null." if "pan" in data else MISSING]
    cin_llpin = values["cin_llpin"]
    if cin_llpin is not None and (not isinstance(cin_llpin, str) or len(cin_llpin) > 21):
        errors["cin_llpin"] = ["Length must be between 1 and 21."]

    phone = data.get("phone")
    if phone is None:
        errors["phone"] = [MISSING]
    elif not isinstance(phone, str) or not PHONE_FORMAT.match(phone):
        errors["phone"] = ["Enter a 10-digit mobile number."]
    values["phone"] = phone
    if errors:
        raise validation_error(errors)

    # Fields that are required only for some businesses.
    if values["gst_registered"] and not values["gstin"]:
        errors["gstin"] = ["Enter your GSTIN (you said you are GST registered)."]
    if values["gst_composition"] and not values["gst_registered"]:
        errors["gst_composition"] = ["Only a GST-registered business can use composition."]
    if values["deducts_tds"] and not values["tan"]:
        errors["tan"] = ["Enter your TAN (you said you deduct TDS)."]
    if values["entity_type"] in COMPANY_TYPES and not values["cin_llpin"]:
        errors["cin_llpin"] = ["Enter your CIN (company) or LLPIN (LLP)."]
    if values["gst_registered"] and values["gstin"]:
        problem = gstin_error(values["gstin"], values["pan"], values["state"])
        if problem:
            errors["gstin"] = [problem]
    if errors:
        raise validation_error(errors)

    # Forget values that do not apply, e.g. a GSTIN sent with gst_registered = false.
    if not values["gst_registered"]:
        values["gstin"] = None
    if not values["deducts_tds"]:
        values["tan"] = None
    if not values["gst_registered"] or values["gst_composition"]:
        values["gst_qrmp"] = False
    if values["entity_type"] not in (EntityType.PARTNERSHIP, EntityType.LLP):
        values["accounts_audited_other_law"] = False
    if values["entity_type"] not in COMPANY_TYPES:
        values["cin_llpin"] = None
    return values


# --- JSON shapes -------------------------------------------------------------------------


def business_to_dict(business: Business) -> dict:
    """The business as its owner sees it (all fields, decrypted)."""
    return {
        "id": str(business.id),
        "legal_name": business.legal_name,
        "entity_type": business.entity_type,
        "state": business.state,
        "address": business.address,
        "description": business.description,
        "annual_turnover": money(business.annual_turnover),
        "investment_amount": money(business.investment_amount),
        "pan": business.pan,
        "phone": business.phone,
        "gst_registered": business.gst_registered,
        "gstin": business.gstin,
        "gst_composition": business.gst_composition,
        "gst_qrmp": business.gst_qrmp,
        "accounts_audited_other_law": business.accounts_audited_other_law,
        "deducts_tds": business.deducts_tds,
        "tan": business.tan,
        "pays_salary_above_limit": business.pays_salary_above_limit,
        "cin_llpin": business.cin_llpin,
        "udyam_number": business.udyam_number,
        # A state typed before the state list existed: the form asks for it again.
        "state_needs_review": state_code(business.state) is None,
    }


def profile_to_dict(profile: RegulatoryProfile | None) -> dict | None:
    if profile is None:
        return None
    return {
        "msme_tier": profile.msme_tier,
        "gst_scheme": profile.gst_scheme,
        "gst_registration_suggested": profile.gst_registration_suggested,
        "itr_form": profile.itr_form,
        "presumptive_eligible": profile.presumptive_eligible,
        "audit_applicable": profile.audit_applicable,
        "other_audit_applicable": profile.other_audit_applicable,
        "files_24q": profile.files_24q,
        "files_26q": profile.files_26q,
        "roc_not_tracked": profile.roc_not_tracked,
        "explanations": profile.explanations,
        "rule_version": profile.rule_version,
        "computed_at": iso(profile.computed_at),
    }


def nic_to_dict(nic: NicCode | None) -> dict | None:
    if nic is None:
        return None
    return {"code": nic.code, "description": nic.description}


def business_page(business: Business) -> dict:
    """{business, profile, nic_code}: what the business page shows."""
    return {
        "business": business_to_dict(business),
        "profile": profile_to_dict(get_profile(business)),
        "nic_code": nic_to_dict(nic_code_of(business)),
    }


def get_profile(business: Business) -> RegulatoryProfile | None:
    return db.session.scalar(
        select(RegulatoryProfile).where(RegulatoryProfile.business_id == business.id)
    )


def nic_code_of(business: Business) -> NicCode | None:
    if business.nic_code_id is None:
        return None
    return db.session.get(NicCode, business.nic_code_id)


# --- The regulatory profile --------------------------------------------------------------


def get_threshold(key: str, today: date) -> Decimal:
    """The legal value `key` from rule_thresholds: the row with the latest effective_from
    up to today."""
    row = db.session.scalar(
        select(RuleThreshold)
        .where(RuleThreshold.key == key, RuleThreshold.effective_from <= today)
        .order_by(RuleThreshold.effective_from.desc())
    )
    if row is None:
        raise ApiError(500, "RULE_MISSING", f"The rule '{key}' is missing. Run `flask seed`.")
    return row.value


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
        max_investment = get_threshold(f"msme.{tier}.max_investment", today)
        max_turnover = get_threshold(f"msme.{tier}.max_turnover", today)
        if investment <= max_investment and turnover <= max_turnover:
            msme_tier = tier
            why["msme_tier"] = (
                f"Investment {format_inr(investment)} is within {format_inr(max_investment)} and "
                f"turnover {format_inr(turnover)} is within {format_inr(max_turnover)}."
            )
            break

    # 2. GST scheme.
    registration_limit = get_threshold("gst.registration.min_turnover", today)
    composition_limit = get_threshold("gst.composition.max_turnover", today)
    qrmp_limit = get_threshold("gst.qrmp.max_turnover", today)
    gst_registration_suggested = False
    if not business.gst_registered:
        gst_scheme = GstScheme.NOT_REGISTERED
        if turnover > registration_limit:
            gst_registration_suggested = True
            why["gst_scheme"] = (
                f"Not registered, but turnover is above {format_inr(registration_limit)}: "
                "you may need GST registration. Ask a CA."
            )
        else:
            why["gst_scheme"] = (
                f"Not registered; turnover is within {format_inr(registration_limit)}."
            )
    elif business.gst_composition and turnover <= composition_limit:
        gst_scheme = GstScheme.COMPOSITION
        why["gst_scheme"] = (
            "You chose the composition scheme and turnover is within "
            f"{format_inr(composition_limit)}."
        )
    else:
        note = ""
        if business.gst_composition:
            note = f"Composition is not allowed above {format_inr(composition_limit)}. "
        if turnover > qrmp_limit:
            gst_scheme = GstScheme.REGULAR_MONTHLY
            why["gst_scheme"] = (
                f"{note}Turnover is above {format_inr(qrmp_limit)}, so returns are monthly "
                "(quarterly QRMP is not allowed)."
            )
        elif business.gst_qrmp:
            gst_scheme = GstScheme.REGULAR_QRMP
            why["gst_scheme"] = (
                f"{note}You chose quarterly returns (QRMP), allowed because turnover is within "
                f"{format_inr(qrmp_limit)}."
            )
        else:
            gst_scheme = GstScheme.REGULAR_MONTHLY
            why["gst_scheme"] = (
                f"{note}You chose monthly returns. Quarterly (QRMP) is also allowed within "
                f"{format_inr(qrmp_limit)}."
            )

    # 3. Presumptive scheme (section 44AD; section 58 of the 2025 Act): individuals, proprietors
    #    and partnership firms.
    presumptive_limit = get_threshold("itr.presumptive_44ad.max_turnover", today)
    if entity in COMPANY_TYPES:
        presumptive_eligible = False
        why["presumptive_eligible"] = "LLPs and companies cannot use the presumptive scheme."
    elif turnover <= presumptive_limit:
        presumptive_eligible = True
        why["presumptive_eligible"] = f"Turnover is within {format_inr(presumptive_limit)}."
    else:
        presumptive_eligible = False
        why["presumptive_eligible"] = f"Turnover is above {format_inr(presumptive_limit)}."

    # 4. Audits (either one moves the ITR due date later).
    # 4a. Tax audit under section 44AB (section 63 of the 2025 Act), from turnover.
    audit_limit = get_threshold("itr.audit_44ab.min_turnover", today)
    if presumptive_eligible:
        audit_applicable = False
        why["audit_applicable"] = "No tax audit when you use the presumptive scheme."
    elif turnover > audit_limit:
        audit_applicable = True
        why["audit_applicable"] = f"Turnover is above {format_inr(audit_limit)}."
    else:
        audit_applicable = False
        why["audit_applicable"] = f"Turnover is within {format_inr(audit_limit)}."

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
    roc_not_tracked = entity in COMPANY_TYPES
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


# --- NIC activity code -------------------------------------------------------------------
#
# 1. Keyword shortlist: the codes whose description contains the most words of the
#    business's own description (real codes only, from the nic_codes table).
# 2. Gemini picks the best 3 from that shortlist and says why. A code that is not in
#    the shortlist is thrown away, so Gemini can never invent a code.
# 3. Fewer than 3 good picks (or no Gemini): the top keyword matches fill the gap.
# 4. The user confirms one code; nothing is saved before that.

NIC_SHORTLIST_SIZE = 15
NIC_PICKS = 3
NIC_SEARCH_LIMIT = 20

# Words that say nothing about the activity; they are not used for matching.
COMMON_WORDS = {
    "and", "the", "for", "with", "our", "are", "from", "all", "any", "also", "into", "its",
    "this", "that", "who", "we", "you", "your", "they", "them", "their", "have", "has",
    "business", "company", "firm", "services", "service", "work", "working", "provide",
    "providing", "products", "product", "sell", "selling", "sale", "sales", "other", "etc",
    "like", "such", "small", "local", "customers", "people", "since", "year", "years",
    "based", "various", "different", "good", "quality", "india", "own", "near", "doing",
    "done", "make", "making", "made",
}  # fmt: skip


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


def _word_in(word: str, text: str) -> bool:
    """Does `text` contain `word`? Longer words also match as the start of a word
    ("bake" matches "bakery"); 3-letter words only as a whole word ("tea", not "steam")."""
    if len(word) <= 3:
        return re.search(r"\b" + re.escape(word) + r"s?\b", text) is not None
    return re.search(r"\b" + re.escape(word), text) is not None


def shortlist_nic_codes(description: str, limit: int = NIC_SHORTLIST_SIZE) -> list[NicCode]:
    """The codes whose description best matches the words of `description`, best first.

    A word found in few codes says more than a common one ("tea" is in 4 codes,
    "station" in many), so each matching word adds 1 / (number of codes containing it).
    """
    words = _match_words(description)
    if not words:
        return []

    # 1. Which codes contain which words.
    found_in = {word: 0 for word in words}  # word -> how many codes contain it
    matched = []  # (code, [its matching words])
    for nic in db.session.scalars(select(NicCode).order_by(NicCode.code)):
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
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [nic for _, nic in scored[:limit]]


def _nic_prompt(description: str, shortlist: list[NicCode]) -> str:
    """The question for Gemini: the description and the shortlist, nothing else."""
    lines = [f"{nic.code}: {nic.description}" for nic in shortlist]
    return (
        "You help an Indian small business choose its NIC-2008 activity code.\n"
        f"Business description: {description}\n\n"
        "Choose the 3 codes from this list that best fit the business, best first:\n"
        + "\n".join(lines)
        + "\n\nUse only codes from the list. For each, give a one-sentence reason.\n"
        'Reply with JSON only: {"picks": [{"code": "...", "reason": "..."}]}'
    )


def _pick(nic: NicCode, reason: str, source: str) -> dict:
    return {"code": nic.code, "description": nic.description, "reason": reason, "source": source}


def _already_picked(picks: list[dict], code: str) -> bool:
    return any(pick["code"] == code for pick in picks)


def _ai_picks(reply: str, shortlist: list[NicCode]) -> list[dict]:
    """The valid picks in Gemini's reply: codes from the shortlist only, no repeats, at most 3."""
    try:
        data = json.loads(reply)
    except ValueError:
        log.warning("Gemini's NIC reply was not JSON")
        return []
    if not isinstance(data, dict) or not isinstance(data.get("picks"), list):
        return []

    allowed = {nic.code: nic for nic in shortlist}
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


def suggest_nic_codes(business: Business) -> dict:
    """Up to 3 suggested NIC codes for the business (nothing is saved).

    Returns {"picks": [{code, description, reason, source: "ai" | "keywords"}],
    "shortlist": [{code, description}], "ai_used": bool}.
    """
    shortlist = shortlist_nic_codes(business.description)

    picks = []
    if shortlist and utils.gemini_available():
        try:
            reply = utils.ask_gemini(_nic_prompt(business.description, shortlist), want_json=True)
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

    shortlist = [nic_to_dict(nic) for nic in shortlist]
    return {"picks": picks, "shortlist": shortlist, "ai_used": ai_used}


# --- Routes ------------------------------------------------------------------------------


@bp.post("/onboarding/business")
@roles_required(UserRole.BUSINESS)
def register_business():
    """Save the business, compute its profile and create this year's filings."""
    values = read_business_form(json_body())
    user = current_user()
    if db.session.scalar(select(Business.id).where(Business.user_id == user.id)):
        raise ApiError(409, "BUSINESS_EXISTS", "You have already registered your business.")

    business = Business(user_id=user.id, **values)
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
    return jsonify(business_page(business)), 201


@bp.get("/onboarding/business")
@roles_required(UserRole.BUSINESS)
def get_business_page():
    return jsonify(business_page(current_business()))


@bp.put("/onboarding/business")
@roles_required(UserRole.BUSINESS)
def update_business():
    """Save the edited form, recompute the profile and sync this year's filings. The answer
    also says what changed: the profile lines, and filings added, removed, or kept although
    no longer needed because a CA has them."""
    from app import marketplace  # imported here: marketplace imports this module

    business = current_business()
    values = read_business_form(json_body())
    for field, value in values.items():
        setattr(business, field, value)

    today = today_in_india()
    profile = get_profile(business)
    old = {line: getattr(profile, line) for line in COMPARED_LINES}
    for field, value in compute_profile(business, today).items():
        setattr(profile, field, value)
    profile.computed_at = utcnow()

    filing_ids = [filing.id for filing in compliance.list_filings(business)]
    keep = marketplace.open_filing_ids(filing_ids)
    filings = compliance.sync_filings(business.id, profile, today, keep)
    db.session.commit()

    changed = []
    for line in COMPARED_LINES:
        new = getattr(profile, line)
        if new != old[line]:
            changed.append({"line": line, "old": old[line], "new": new})
    log.info("Business %s updated: %d profile lines changed", business.id, len(changed))
    page = business_page(business)
    page["changes"] = {"profile": changed, "filings": filings}
    return jsonify(page)


@bp.post("/onboarding/nic-suggestions")
@roles_required(UserRole.BUSINESS)
def suggest_nic_codes_for_me():
    return jsonify(suggest_nic_codes(current_business()))


@bp.get("/onboarding/nic-codes")
@roles_required(UserRole.BUSINESS)
def search_nic_codes():
    """Up to 20 codes whose code or description contains `q` (choosing a code by hand)."""
    query = request.args.get("q", "")
    if len(query) > 100:
        raise validation_error({"q": ["Longer than maximum length 100."]}, "query")
    query = query.strip()
    if len(query) < 2:
        return jsonify([])
    pattern = f"%{query}%"
    stmt = (
        select(NicCode)
        .where(or_(NicCode.code.ilike(pattern), NicCode.description.ilike(pattern)))
        .order_by(NicCode.code)
        .limit(NIC_SEARCH_LIMIT)
    )
    return jsonify([nic_to_dict(nic) for nic in db.session.scalars(stmt)])


@bp.put("/onboarding/business/nic-code")
@roles_required(UserRole.BUSINESS)
def set_nic_code():
    """Save the NIC code the user confirmed. 422 UNKNOWN_NIC_CODE if it is not in the list."""
    code = json_body().get("code")
    if code is None:
        raise validation_error({"code": [MISSING]})
    if not isinstance(code, str) or not 1 <= len(code) <= 10:
        raise validation_error({"code": ["Length must be between 1 and 10."]})
    business = current_business()
    nic = db.session.scalar(select(NicCode).where(NicCode.code == code.strip()))
    if nic is None:
        raise ApiError(422, "UNKNOWN_NIC_CODE", "Choose a code from the NIC list.")
    business.nic_code_id = nic.id
    db.session.commit()
    log.info("Business %s chose NIC code %s", business.id, nic.code)
    return jsonify(nic_to_dict(nic))


@bp.get("/onboarding/states")
@roles_required(UserRole.BUSINESS)
def list_states():
    """The states and union territories with their GST codes, for the form."""
    return jsonify([{"name": state["name"], "code": state["code"]} for state in GST_STATES])


@bp.post("/onboarding/autofill")
@roles_required(UserRole.BUSINESS)
def autofill():
    """Read a GST certificate or PAN card locally and suggest form values. The file is read
    in memory and thrown away; the user checks the values in the form first."""
    upload = request.files.get("file")
    if upload is None:
        raise validation_error({"file": [MISSING]}, "files")
    data = upload.read()
    utils.check_file(data, upload.mimetype)
    try:
        text = ocr.extract_text(data, upload.mimetype)
    except ocr.OcrError as error:
        raise ApiError(
            422, "DOCUMENT_UNREADABLE", f"We could not read this file. {error}"
        ) from error
    found = ocr.read_registration(text)
    log.info("Auto-fill read %d field(s) from a document", len(found))
    return jsonify({"found": found})


# --- For other modules -------------------------------------------------------------------


def get_business(business_id) -> Business | None:
    return db.session.get(Business, business_id)


def business_of_user(user: User) -> Business | None:
    """The user's business, or None before registration."""
    return db.session.scalar(select(Business).where(Business.user_id == user.id))


def get_msme_tier(business: Business) -> str | None:
    """The MSME tier of the business's profile, e.g. "micro" (None without a profile)."""
    profile = get_profile(business)
    return profile.msme_tier if profile else None


def get_itr_form(business: Business) -> str | None:
    """The ITR form of the business's profile, e.g. "itr_5" (None without a profile)."""
    profile = get_profile(business)
    return profile.itr_form if profile else None


def count_businesses() -> int:
    return db.session.scalar(select(func.count(Business.id)))


def business_categories(business_ids) -> list[dict]:
    """{id, user_id, legal_name, entity_type, state, gst_scheme} of these businesses:
    category-level facts only, to match regulatory changes."""
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
    """The businesses with this entity type and MSME tier (peer insights)."""
    stmt = (
        select(Business.id)
        .join(RegulatoryProfile, RegulatoryProfile.business_id == Business.id)
        .where(Business.entity_type == entity_type, RegulatoryProfile.msme_tier == msme_tier)
    )
    return set(db.session.scalars(stmt))


def resync_all_filings(today: date | None = None) -> dict:
    """Match every business's filings of this financial year to the current rules (run by
    `flask seed`), so a corrected due-date rule reaches filings created earlier. Does not
    commit. Returns {"businesses", "added", "removed"}."""
    from app import marketplace  # imported here: marketplace imports this module

    today = today or today_in_india()
    totals = {"businesses": 0, "added": 0, "removed": 0}
    stmt = select(Business, RegulatoryProfile).join(
        RegulatoryProfile, RegulatoryProfile.business_id == Business.id
    )
    for business, profile in db.session.execute(stmt).all():
        filing_ids = [filing.id for filing in compliance.list_filings(business)]
        keep = marketplace.open_filing_ids(filing_ids)
        counts = compliance.sync_filings(business.id, profile, today, keep)
        totals["businesses"] += 1
        totals["added"] += counts["added"]
        totals["removed"] += counts["removed"]
    return totals
