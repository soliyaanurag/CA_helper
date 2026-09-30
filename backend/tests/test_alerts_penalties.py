"""Penalty rules and the estimator (AL4, AL5).

The seeded rules hold the values checked on 29 Sep 2026 (app/seed.py, docs/TODO_VERIFY.md).
The arithmetic tests start from rules with every amount empty (`rules`) and write made-up
amounts into the test database only: they are NOT legal values.

The `business_with_filings` QRMP business: GSTR-1 for Q1 2026-27 was due on 13 Jul 2026,
GSTR-3B for Q1 on 22 Jul 2026, GSTR-1 for Q2 on 13 Oct 2026.
"""

from datetime import date
from decimal import Decimal

import pytest

from app import alerts as alerts_service
from app.models import (
    Business,
    ComplianceItem,
    ComplianceStatus,
    EntityType,
    PenaltyRule,
    today_in_india,
    User,
    UserRole,
)
from app.seed import PENALTY_COLUMNS, PENALTY_RULES, seed_penalty_rules

BASE = "/api/v1/alerts"


@pytest.fixture()
def seeded(database):
    """The seeded penalty rules, as {form code: PenaltyRule}."""
    seed_penalty_rules()
    database.session.commit()
    return {rule.form_code: rule for rule in database.session.query(PenaltyRule)}


@pytest.fixture()
def rules(seeded, database):
    """The seeded rules with every amount emptied, for the made-up amounts of the tests."""
    for rule in seeded.values():
        for column in PENALTY_COLUMNS:
            setattr(rule, column, None)
    database.session.commit()
    return seeded


def filing(database, form_code, period_label) -> ComplianceItem:
    return (
        database.session.query(ComplianceItem)
        .filter_by(form_code=form_code, period_label=period_label)
        .one()
    )


def estimate(business, item, tax_due=None, today=date(2026, 7, 23)):
    return alerts_service.estimate_penalty(business, item.id, tax_due, today=today)


# --- AL4: the seeded rules ----------------------------------------------------------------


def test_every_form_has_a_rule_with_its_seeded_values(seeded, database):
    assert set(seeded) == {form for form, _, _ in PENALTY_RULES}
    assert len(seeded) == 7
    for form, amounts, source in PENALTY_RULES:
        rule = seeded[form]
        assert rule.source_reference == source
        for column in PENALTY_COLUMNS:
            expected = amounts.get(column)
            assert getattr(rule, column) == (Decimal(expected) if expected else None)
    # The TDS late fee is confirmed; the GST interest rate is not yet.
    assert "TODO_VERIFY" not in seeded["tds_24q"].source_reference
    assert "TODO_VERIFY" in seeded["gstr_3b"].source_reference

    seed_penalty_rules()  # running the seed again adds nothing
    database.session.commit()
    assert database.session.query(PenaltyRule).count() == 7


def test_the_seed_updates_a_rule_seeded_earlier(seeded, database):
    old = seeded["gstr_3b"]
    old.late_fee_per_day = None  # as the first seed left it
    old.source_reference = "TODO_VERIFY: old text"
    database.session.commit()

    seed_penalty_rules()
    database.session.commit()

    assert old.late_fee_per_day == Decimal("50")
    assert old.source_reference.startswith("CBIC Circular 26/26/2017-GST")


def test_the_seeded_gst_rules_give_an_estimate(business_with_filings, seeded, database):
    # GSTR-1 Q1 was due on 13 Jul: 10 days × ₹50, under the ₹2,000 cap; no interest.
    result = estimate(business_with_filings, filing(database, "gstr_1", "Q1 2026-27"))
    assert (result["status"], result["late_fee"], result["total"]) == (
        "estimated",
        Decimal("500.00"),
        Decimal("500.00"),
    )
    assert result["label"] == "Estimate (rules pending verification)"
    long_late = estimate(
        business_with_filings, filing(database, "gstr_1", "Q1 2026-27"), today=date(2026, 12, 1)
    )
    assert long_late["late_fee"] == Decimal("2000.00")


def test_cmp08_has_no_late_fee(seeded):
    assert seeded["cmp_08"].late_fee_per_day == Decimal("0")
    assert seeded["cmp_08"].max_late_fee == Decimal("0")


# --- AL5: the estimate --------------------------------------------------------------------


def test_unconfirmed_rules_give_a_pending_estimate(business_with_filings, rules, database):
    result = estimate(business_with_filings, filing(database, "gstr_1", "Q1 2026-27"))

    assert result["status"] == "pending"
    assert result["days_late"] == 10  # due 13 Jul, today 23 Jul
    assert (result["late_fee"], result["interest"], result["total"]) == (None, None, None)
    assert result["notes"] == [
        "The late fee for this form is not confirmed yet.",
        "The interest rate is not confirmed yet.",
    ]
    assert result["label"] == "Estimate (rules pending verification)"


def test_a_form_without_a_rule_is_pending(business_with_filings, database):
    result = estimate(business_with_filings, filing(database, "gstr_1", "Q1 2026-27"))

    assert result["status"] == "pending"
    assert result["notes"] == ["There is no penalty rule for this form yet."]


def test_late_fee_is_days_times_the_daily_fee_up_to_the_cap(business_with_filings, rules, database):
    rules["gstr_1"].late_fee_per_day = Decimal("10")  # made-up test amounts
    rules["gstr_1"].max_late_fee = Decimal("150")
    database.session.commit()
    item = filing(database, "gstr_1", "Q1 2026-27")

    ten_days = estimate(business_with_filings, item)
    assert (ten_days["status"], ten_days["late_fee"], ten_days["total"]) == (
        "estimated",
        Decimal("100.00"),
        Decimal("100.00"),
    )
    assert ten_days["notes"] == ["The interest rate is not confirmed yet."]
    capped = estimate(business_with_filings, item, today=date(2026, 8, 13))
    assert capped["late_fee"] == Decimal("150.00")


def test_a_flat_fee_is_charged_once_however_late(business_with_filings, rules, database):
    rules["gstr_1"].flat_late_fee = Decimal("500")
    rules["gstr_1"].late_fee_per_day = Decimal("10")  # ignored when a flat fee is set
    database.session.commit()
    item = filing(database, "gstr_1", "Q1 2026-27")

    assert estimate(business_with_filings, item)["late_fee"] == Decimal("500.00")
    later = estimate(business_with_filings, item, today=date(2026, 12, 1))
    assert later["late_fee"] == Decimal("500.00")


def test_interest_needs_the_tax_due(business_with_filings, rules, database):
    rules["gstr_1"].late_fee_per_day = Decimal("10")
    rules["gstr_1"].annual_interest_rate = Decimal("12")
    database.session.commit()
    item = filing(database, "gstr_1", "Q1 2026-27")

    without = estimate(business_with_filings, item)
    assert without["interest"] is None
    assert without["notes"] == ["Enter the tax due to estimate the interest."]

    # 36,500 × 12% × 10 days / 365 = 120
    with_tax = estimate(business_with_filings, item, tax_due=Decimal("36500"))
    assert with_tax["interest"] == Decimal("120.00")
    assert with_tax["total"] == Decimal("220.00")
    assert with_tax["notes"] == []


def test_the_rule_in_force_on_the_due_date_is_used(business_with_filings, rules, database):
    rules["gstr_1"].late_fee_per_day = Decimal("10")
    rules["gstr_1"].effective_to = date(2026, 10, 1)
    database.session.add(
        PenaltyRule(
            form_code="gstr_1",
            late_fee_per_day=Decimal("20"),
            source_reference="made-up test rule",
            effective_from=date(2026, 10, 1),
        )
    )
    database.session.commit()
    today = date(2026, 10, 23)

    q1 = estimate(business_with_filings, filing(database, "gstr_1", "Q1 2026-27"), today=today)
    q2 = estimate(business_with_filings, filing(database, "gstr_1", "Q2 2026-27"), today=today)

    assert q1["late_fee"] == Decimal("1020.00")  # 102 days × 10, the rule of 13 Jul
    assert q2["late_fee"] == Decimal("200.00")  # 10 days × 20, the rule of 13 Oct
    assert q2["label"] == "Estimate"  # that rule is not marked TODO_VERIFY


def test_not_late_and_filed_filings_have_no_penalty(business_with_filings, rules, database):
    rules["gstr_1"].late_fee_per_day = Decimal("10")
    q1 = filing(database, "gstr_1", "Q1 2026-27")
    q1.status = ComplianceStatus.FILED
    database.session.commit()

    assert estimate(business_with_filings, q1)["status"] == "filed"
    q2 = estimate(business_with_filings, filing(database, "gstr_1", "Q2 2026-27"))
    assert (q2["status"], q2["days_late"], q2["late_fee"]) == ("not_late", 0, None)


def test_exposure_adds_the_late_fees_of_overdue_filings(business_with_filings, rules, database):
    rules["gstr_1"].late_fee_per_day = Decimal("10")
    rules["gstr_1"].annual_interest_rate = Decimal("12")  # interest is never in the total
    database.session.commit()

    result = alerts_service.penalty_exposure(business_with_filings, today=date(2026, 7, 23))

    # Late on 23 Jul: GSTR-1 Q1 (10 days) and GSTR-3B Q1 (1 day, no confirmed amount).
    assert result["overdue_count"] == 2
    assert (result["estimated_count"], result["pending_count"]) == (1, 1)
    assert result["total_late_fees"] == Decimal("100.00")
    assert result["label"] == "Estimate (rules pending verification)"


# --- The endpoints ---------------------------------------------------------------------


def test_filing_estimate_endpoint(client, business_with_filings, rules, auth_headers, database):
    rules["gstr_1"].late_fee_per_day = Decimal("10")
    rules["gstr_1"].annual_interest_rate = Decimal("12")
    database.session.commit()
    owner = database.session.get(User, business_with_filings.user_id)
    item = filing(database, "gstr_1", "Q1 2026-27")
    days = (today_in_india() - item.due_date).days

    response = client.get(f"{BASE}/penalties/{item.id}?tax_due=36500", headers=auth_headers(owner))

    data = response.get_json()
    assert response.status_code == 200
    assert data["days_late"] == days
    assert data["late_fee"] == f"{10 * days:.2f}"
    assert data["interest"] == f"{Decimal(36500) * 12 / 100 * days / 365:.2f}"
    assert data["form_code"] == "gstr_1"


def test_exposure_endpoint(client, business_with_filings, rules, auth_headers, database):
    owner = database.session.get(User, business_with_filings.user_id)

    response = client.get(f"{BASE}/penalties", headers=auth_headers(owner))

    data = response.get_json()
    assert response.status_code == 200
    assert data["total_late_fees"] == "0.00"
    assert data["pending_count"] == data["overdue_count"]
    assert data["label"] == "Estimate (rules pending verification)"


def test_another_business_cannot_see_the_estimate(
    client, business_with_filings, make_user, auth_headers, database
):
    item = filing(database, "gstr_1", "Q1 2026-27")
    stranger = make_user(role=UserRole.BUSINESS)
    database.session.add(
        Business(
            user_id=stranger.id,
            legal_name="Other Shop",
            entity_type=EntityType.INDIVIDUAL,
            state="Kerala",
            address="Kochi",
            description="Tutor",
            annual_turnover=500_000,
            investment_amount=0,
            pan="PQRSX6789K",
            phone="9123456780",
            gst_registered=False,
            deducts_tds=False,
            pays_salary_above_limit=False,
        )
    )
    database.session.commit()

    response = client.get(f"{BASE}/penalties/{item.id}", headers=auth_headers(stranger))

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "FILING_NOT_FOUND"


@pytest.mark.parametrize("role", [UserRole.CA, UserRole.ADMIN])
def test_penalties_are_for_businesses_only(client, make_user, auth_headers, database, role):
    headers = auth_headers(make_user(role=role))
    assert client.get(f"{BASE}/penalties", headers=headers).status_code == 403


def test_a_negative_tax_due_is_rejected(client, business_with_filings, auth_headers, database):
    owner = database.session.get(User, business_with_filings.user_id)
    item = filing(database, "gstr_1", "Q1 2026-27")

    response = client.get(f"{BASE}/penalties/{item.id}?tax_due=-5", headers=auth_headers(owner))

    assert response.status_code == 422
