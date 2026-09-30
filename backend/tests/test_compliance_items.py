"""Creating and syncing filings from the profile (compliance_service, CO3) and listing them."""

from datetime import date

import pytest

from app.compliance import create_filings, sync_filings
from app.models import (
    Business,
    ComplianceItem,
    ComplianceStatus,
    EntityType,
    GstScheme,
    RegulatoryProfile,
    User,
    UserRole,
)

TODAY = date(2026, 9, 27)
URL = "/api/v1/compliance/items"


@pytest.fixture()
def business(make_user, legal_rules, database):
    owner = make_user(role=UserRole.BUSINESS)
    business = Business(
        user_id=owner.id,
        legal_name="Asha Traders",
        entity_type=EntityType.PROPRIETORSHIP,
        state="Maharashtra",
        address="Pune",
        description="Retail shop",
        annual_turnover=4_500_000,
        investment_amount=800_000,
        pan="ABCDE1234F",
        phone="9876543210",
        gst_registered=True,
        gstin="27ABCDE1234F1Z5",
        deducts_tds=True,
        tan="PNEA12345B",
        pays_salary_above_limit=False,
    )
    database.session.add(business)
    database.session.commit()
    return business


def profile(**changes) -> RegulatoryProfile:
    """Only the fields that decide which forms apply (not saved)."""
    fields = {
        "gst_scheme": GstScheme.REGULAR_QRMP,
        "audit_applicable": False,
        "files_24q": False,
        "files_26q": True,
    }
    fields.update(changes)
    return RegulatoryProfile(**fields)


def items(database) -> list[ComplianceItem]:
    return database.session.query(ComplianceItem).order_by(ComplianceItem.due_date).all()


def test_qrmp_business_with_tds(business, database):
    added = create_filings(business.id, profile(), TODAY)
    database.session.commit()

    by_form = {}
    for item in items(database):
        by_form.setdefault(item.form_code, []).append(item.period_label)
    assert added == len(items(database))
    # Every quarter from 1 April (Q1 was due in July, so it is overdue on 27 Sep 2026).
    quarters = ["Q1 2026-27", "Q2 2026-27", "Q3 2026-27", "Q4 2026-27"]
    assert by_form["gstr_1"] == quarters
    assert by_form["gstr_3b"] == quarters
    assert by_form["tds_26q"] == quarters
    assert by_form["itr"] == ["FY 2026-27"]
    assert "tds_24q" not in by_form and "cmp_08" not in by_form


def test_filings_start_upcoming_with_their_dates(business, database):
    create_filings(business.id, profile(), TODAY)
    database.session.commit()

    itr = database.session.query(ComplianceItem).filter_by(form_code="itr").one()
    assert itr.status == "upcoming"
    assert itr.fy == "2026-27"
    assert (itr.period_start, itr.period_end) == (date(2026, 4, 1), date(2027, 3, 31))
    assert itr.due_date >= TODAY


def test_monthly_business_gets_one_filing_per_month(business, database):
    create_filings(business.id, profile(gst_scheme=GstScheme.REGULAR_MONTHLY), TODAY)
    database.session.commit()

    gstr_3b = [item for item in items(database) if item.form_code == "gstr_3b"]
    assert gstr_3b[0].period_label == "Apr 2026"  # from the start of the financial year
    assert gstr_3b[-1].period_label == "Mar 2027"
    assert len(gstr_3b) == 12


def test_composition_business(business, database):
    create_filings(business.id, profile(gst_scheme=GstScheme.COMPOSITION), TODAY)
    database.session.commit()

    forms = {item.form_code for item in items(database)}
    assert forms == {"cmp_08", "gstr_4", "itr", "tds_26q"}


def test_running_again_adds_nothing(business, database):
    first = create_filings(business.id, profile(), TODAY)
    database.session.commit()
    second = create_filings(business.id, profile(), TODAY)
    database.session.commit()

    assert first > 0
    assert second == 0


def test_list_is_sorted_by_due_date(client, business, auth_headers, database):
    create_filings(business.id, profile(), TODAY)
    database.session.commit()
    user = database.session.get(User, business.user_id)
    body = client.get(URL, headers=auth_headers(user)).get_json()

    due_dates = [item["due_date"] for item in body]
    assert len(body) == len(items(database))
    assert due_dates == sorted(due_dates)
    assert set(body[0]) >= {"form_code", "period_label", "due_date", "status"}


def test_list_before_registering_is_404(client, make_user, auth_headers):
    response = client.get(URL, headers=auth_headers(make_user(role=UserRole.BUSINESS)))

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "BUSINESS_NOT_FOUND"


# --- Past filings and syncing after a profile change ----------------------------------


def by_key(database) -> dict:
    """{(form, period label): filing} of the filings."""
    return {(item.form_code, item.period_label): item for item in items(database)}


def test_filings_whose_due_date_passed_start_overdue(business, database):
    create_filings(business.id, profile(), TODAY)
    database.session.commit()

    filings = by_key(database)
    assert filings[("gstr_3b", "Q1 2026-27")].status == ComplianceStatus.OVERDUE
    assert filings[("gstr_3b", "Q2 2026-27")].status == ComplianceStatus.UPCOMING


def test_a_filing_that_no_longer_applies_is_deleted(business, database):
    create_filings(business.id, profile(), TODAY)
    database.session.commit()

    counts = sync_filings(business.id, profile(files_26q=False), TODAY)
    database.session.commit()

    assert counts["removed"] == 4
    assert not any(form == "tds_26q" for form, _ in by_key(database))
    assert database.session.query(ComplianceItem).filter_by(form_code="tds_26q").count() == 0


def test_a_filing_that_applies_again_is_added_again(business, database):
    create_filings(business.id, profile(), TODAY)
    database.session.commit()
    sync_filings(business.id, profile(files_26q=False), TODAY)
    database.session.commit()

    counts = sync_filings(business.id, profile(), TODAY)
    database.session.commit()

    assert counts["added"] == 4
    assert database.session.query(ComplianceItem).filter_by(form_code="tds_26q").count() == 4


def test_filed_and_ca_filings_are_kept(business, database):
    create_filings(business.id, profile(), TODAY)
    database.session.commit()
    filings = by_key(database)
    filings[("tds_26q", "Q1 2026-27")].status = ComplianceStatus.FILED
    filings[("tds_26q", "Q2 2026-27")].status = ComplianceStatus.WITH_CA
    requested = filings[("tds_26q", "Q3 2026-27")]  # in an open request
    database.session.commit()

    counts = sync_filings(business.id, profile(files_26q=False), TODAY, keep_ids={requested.id})
    database.session.commit()

    assert (counts["removed"], counts["kept_with_ca"]) == (1, 2)
    left = {period for form, period in by_key(database) if form == "tds_26q"}
    assert left == {"Q1 2026-27", "Q2 2026-27", "Q3 2026-27"}


def test_an_audit_moves_the_itr_due_date(business, database):
    create_filings(business.id, profile(), TODAY)
    database.session.commit()
    before = by_key(database)[("itr", "FY 2026-27")].due_date

    counts = sync_filings(business.id, profile(other_audit_applicable=True), TODAY)
    database.session.commit()

    assert counts["moved"] == 1
    assert by_key(database)[("itr", "FY 2026-27")].due_date > before
