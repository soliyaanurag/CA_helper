"""Creating filings from the profile (compliance_service.create_filings, CO3) and listing them."""

from datetime import date

import pytest

from app.models import Business, ComplianceItem, RegulatoryProfile, User
from app.models.enums import UserRole
from app.models.onboarding import EntityType, GstScheme
from app.services.compliance_service import create_filings

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
    # Only periods still due on 27 Sep 2026: Q2, Q3, Q4 (Q1 was due in July).
    assert by_form["gstr_1"] == ["Q2 2026-27", "Q3 2026-27", "Q4 2026-27"]
    assert by_form["gstr_3b"] == ["Q2 2026-27", "Q3 2026-27", "Q4 2026-27"]
    assert by_form["tds_26q"] == ["Q2 2026-27", "Q3 2026-27", "Q4 2026-27"]
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
    assert gstr_3b[0].period_label == "Sep 2026"  # August's return was due before today
    assert gstr_3b[-1].period_label == "Mar 2027"


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
