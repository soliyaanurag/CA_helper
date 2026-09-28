"""The regulatory profile engine (onboarding_service.compute_profile, ON5 + ON6).

Uses the seeded rule thresholds (the `legal_rules` fixture), so the numbers below
follow app/seed.py; they are marked TODO_VERIFY there until someone checks them.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models import Business, RuleThreshold
from app.models.onboarding import EntityType, GstScheme, ItrForm, MsmeTier
from app.services.onboarding_service import compute_profile

TODAY = date(2026, 9, 27)
LAKH = Decimal("100000")
CRORE = Decimal("10000000")


def make_business(**changes) -> Business:
    """A small, GST-registered proprietorship (not saved: the engine only reads it)."""
    fields = {
        "entity_type": EntityType.PROPRIETORSHIP,
        "annual_turnover": 50 * LAKH,
        "investment_amount": 10 * LAKH,
        "gst_registered": True,
        "gst_composition": False,
        "gst_qrmp": True,  # chose quarterly returns
        "accounts_audited_other_law": False,
        "deducts_tds": False,
        "pays_salary_above_limit": False,
    }
    fields.update(changes)
    return Business(**fields)


@pytest.fixture(autouse=True)
def _rules(legal_rules):
    pass


def test_small_proprietor():
    profile = compute_profile(make_business(), TODAY)

    assert profile["msme_tier"] == MsmeTier.MICRO
    assert profile["gst_scheme"] == GstScheme.REGULAR_QRMP
    assert profile["presumptive_eligible"] is True
    assert profile["audit_applicable"] is False
    assert profile["itr_form"] == ItrForm.ITR_4
    assert profile["files_24q"] is False and profile["files_26q"] is False
    assert profile["roc_not_tracked"] is False


def test_every_line_has_a_why():
    profile = compute_profile(make_business(), TODAY)

    for line in ("msme_tier", "gst_scheme", "presumptive_eligible", "audit_applicable", "itr_form"):
        assert profile["explanations"][line]
    assert "₹" in profile["explanations"]["msme_tier"]


@pytest.mark.parametrize(
    ("investment", "turnover", "tier"),
    [
        (2 * CRORE, 8 * CRORE, MsmeTier.MICRO),
        (3 * CRORE, 8 * CRORE, MsmeTier.SMALL),  # investment above the micro limit
        (2 * CRORE, 200 * CRORE, MsmeTier.MEDIUM),  # turnover above the small limit
        (200 * CRORE, 50 * CRORE, MsmeTier.NOT_MSME),  # investment above every limit
    ],
)
def test_msme_tier_needs_both_limits(investment, turnover, tier):
    profile = compute_profile(
        make_business(investment_amount=investment, annual_turnover=turnover), TODAY
    )

    assert profile["msme_tier"] == tier


def test_gst_scheme():
    assert compute_profile(make_business(annual_turnover=6 * CRORE), TODAY)["gst_scheme"] == (
        GstScheme.REGULAR_MONTHLY
    )
    assert compute_profile(make_business(gst_composition=True), TODAY)["gst_scheme"] == (
        GstScheme.COMPOSITION
    )


def test_composition_above_its_limit_falls_back_to_regular():
    profile = compute_profile(make_business(gst_composition=True, annual_turnover=2 * CRORE), TODAY)

    assert profile["gst_scheme"] == GstScheme.REGULAR_QRMP
    assert "Composition is not allowed" in profile["explanations"]["gst_scheme"]


def test_unregistered_business_above_the_limit_is_told_to_register():
    small = compute_profile(make_business(gst_registered=False, annual_turnover=10 * LAKH), TODAY)
    big = compute_profile(make_business(gst_registered=False, annual_turnover=30 * LAKH), TODAY)

    assert small["gst_scheme"] == GstScheme.NOT_REGISTERED
    assert small["gst_registration_suggested"] is False
    assert big["gst_registration_suggested"] is True


def test_bigger_proprietor_needs_an_audit_and_itr_3():
    profile = compute_profile(make_business(annual_turnover=5 * CRORE), TODAY)

    assert profile["presumptive_eligible"] is False
    assert profile["audit_applicable"] is True
    assert profile["itr_form"] == ItrForm.ITR_3


@pytest.mark.parametrize(
    ("entity", "itr_form", "tax_audit", "other_audit"),
    [
        (EntityType.PARTNERSHIP, ItrForm.ITR_4, False, False),  # small firm: presumptive
        (EntityType.LLP, ItrForm.ITR_5, False, False),
        (EntityType.PRIVATE_LIMITED, ItrForm.ITR_6, False, True),  # company law, not s.44AB
    ],
)
def test_itr_form_by_entity(entity, itr_form, tax_audit, other_audit):
    profile = compute_profile(make_business(entity_type=entity), TODAY)

    assert profile["itr_form"] == itr_form
    assert profile["audit_applicable"] is tax_audit
    assert profile["other_audit_applicable"] is other_audit
    assert profile["roc_not_tracked"] is (entity != EntityType.PARTNERSHIP)


def test_qrmp_is_the_users_choice_within_the_limit():
    monthly = compute_profile(make_business(gst_qrmp=False), TODAY)
    quarterly = compute_profile(make_business(gst_qrmp=True), TODAY)
    too_big = compute_profile(make_business(gst_qrmp=True, annual_turnover=6 * CRORE), TODAY)

    assert monthly["gst_scheme"] == GstScheme.REGULAR_MONTHLY
    assert "You chose monthly returns" in monthly["explanations"]["gst_scheme"]
    assert quarterly["gst_scheme"] == GstScheme.REGULAR_QRMP
    assert "You chose quarterly returns (QRMP)" in quarterly["explanations"]["gst_scheme"]
    assert too_big["gst_scheme"] == GstScheme.REGULAR_MONTHLY
    assert "not allowed" in too_big["explanations"]["gst_scheme"]


@pytest.mark.parametrize("entity", [EntityType.PARTNERSHIP, EntityType.LLP])
def test_firms_and_llps_answer_the_other_audit_question(entity):
    audited = compute_profile(
        make_business(entity_type=entity, accounts_audited_other_law=True), TODAY
    )

    assert audited["other_audit_applicable"] is True
    assert "You said your accounts are audited" in audited["explanations"]["other_audit_applicable"]


def test_proprietors_ignore_the_other_audit_answer():
    profile = compute_profile(make_business(accounts_audited_other_law=True), TODAY)

    assert profile["other_audit_applicable"] is False


def test_the_company_audit_is_explained_on_its_own_line():
    profile = compute_profile(make_business(entity_type=EntityType.PRIVATE_LIMITED), TODAY)

    assert "company" not in profile["explanations"]["audit_applicable"].lower()
    assert "always audited" in profile["explanations"]["other_audit_applicable"]


def test_amounts_use_the_indian_number_format():
    profile = compute_profile(make_business(annual_turnover=45 * LAKH), TODAY)

    assert "₹45,00,000" in profile["explanations"]["msme_tier"]


def test_tds_returns():
    other_payments = compute_profile(make_business(deducts_tds=True), TODAY)
    salaries = compute_profile(make_business(deducts_tds=True, pays_salary_above_limit=True), TODAY)

    assert (other_payments["files_24q"], other_payments["files_26q"]) == (False, True)
    assert (salaries["files_24q"], salaries["files_26q"]) == (True, True)


def test_thresholds_come_from_the_table(database):
    """Change a threshold in the table and the result changes: no number is in the code."""
    row = database.session.query(RuleThreshold).filter_by(key="gst.qrmp.max_turnover").one()
    row.value = 10 * LAKH
    database.session.commit()

    assert compute_profile(make_business(), TODAY)["gst_scheme"] == GstScheme.REGULAR_MONTHLY
