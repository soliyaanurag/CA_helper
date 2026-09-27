"""Business logic for onboarding: registering a business and working out its regulatory profile.

register_business(user, data) -> dict     save the business, compute its profile, create its filings
update_business(business, data) -> dict   edit: recompute profile, sync filings, say what changed
get_my_business(business) -> dict         the business with its profile
list_states() -> list[dict]               the states / UTs for the form, with their GST codes
compute_profile(business, today) -> dict  the profile values plus a "why" for each (ON5, ON6)
get_business(business_id) -> Business     one business by id (used by marketplace)
get_itr_form(business) -> str | None      its profile's ITR form, e.g. "itr_5" (used by marketplace)

The profile is computed from legal thresholds stored in `rule_thresholds` (read
with _threshold()); no legal number is written in this file (CLAUDE.md rule 3).
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select

from app.errors import ApiError
from app.extensions import db
from app.models import Business, RegulatoryProfile, RuleThreshold, User
from app.models.base import today_in_india, utcnow
from app.models.onboarding import EntityType, GstScheme, ItrForm, MsmeTier
from app.services import compliance_service
from app.utils.gstin import GST_STATES
from app.utils.money import format_inr

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

    # 3. Presumptive scheme (section 44AD): individuals, proprietors and partnership firms.
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
    # 4a. Tax audit under section 44AB, from turnover.
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
        select(Business.id).where(Business.user_id == user.id, Business.deleted_at.is_(None))
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
    added = compliance_service.create_filings(business.id, profile, today)

    db.session.commit()
    log.info("Business %s registered with %d filings", business.id, added)
    return {"business": business, "profile": profile}


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
    # Imported here: marketplace_service imports this module (a top-level import would loop).
    from app.services import marketplace_service

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

    filing_ids = [filing.id for filing in compliance_service.list_filings(business)]
    keep = marketplace_service.open_filing_ids(filing_ids)
    filings = compliance_service.sync_filings(business.id, profile, today, keep)
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
        "changes": {"profile": changed, "filings": filings},
    }


def list_states() -> list[dict]:
    """The states and union territories with their GST codes (reference data)."""
    return GST_STATES


def get_my_business(business: Business) -> dict:
    """The business together with its regulatory profile."""
    profile = db.session.scalar(
        select(RegulatoryProfile).where(RegulatoryProfile.business_id == business.id)
    )
    return {"business": business, "profile": profile}


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
    return profile.itr_form.value


def count_businesses() -> int:
    """How many live businesses are registered (admin dashboard)."""
    return db.session.scalar(select(func.count(Business.id)).where(Business.deleted_at.is_(None)))


def business_of_user(user: User) -> Business | None:
    """The user's live business, or None before registration (used by marketplace)."""
    return db.session.scalar(
        select(Business).where(Business.user_id == user.id, Business.deleted_at.is_(None))
    )
