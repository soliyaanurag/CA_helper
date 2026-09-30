"""GET /api/v1/compliance/dashboard: the business home page numbers (CO12), business role only."""

from datetime import date

import pytest

from app import compliance as compliance_service
from app.models import ComplianceItem, ComplianceStatus, User, UserRole

URL = "/api/v1/compliance/dashboard"


def test_welcomes_a_user_who_has_not_registered_yet(client, make_user, auth_headers):
    user = make_user(role=UserRole.BUSINESS, full_name="Meera Shah")

    response = client.get(URL, headers=auth_headers(user))

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "Welcome, Meera Shah",
        "registered": False,
        "next_deadline": None,
        "due_this_month": 0,
        "overdue": 0,
        "with_ca": 0,
    }


def test_counts_for_a_registered_business(business_with_filings, database):
    """On 5 Oct 2026: Q1's GSTR-1 and GSTR-3B are late; Q2's are due on 13 and 22 Oct."""
    owner = database.session.get(User, business_with_filings.user_id)

    result = compliance_service.get_dashboard(owner, business_with_filings, date(2026, 10, 5))

    assert result["registered"] is True
    assert result["overdue"] == 2
    assert result["due_this_month"] == 2
    assert result["with_ca"] == 0
    next_filing = result["next_deadline"]
    assert (next_filing.form_code, next_filing.period_label) == ("gstr_1", "Q2 2026-27")


def test_filed_filings_are_not_counted_and_with_ca_ones_are(business_with_filings, database):
    owner = database.session.get(User, business_with_filings.user_id)
    q1 = database.session.query(ComplianceItem).filter_by(period_label="Q1 2026-27").all()
    q1[0].status = ComplianceStatus.FILED
    q1[1].status = ComplianceStatus.WITH_CA
    database.session.commit()

    result = compliance_service.get_dashboard(owner, business_with_filings, date(2026, 10, 5))

    assert result["overdue"] == 1  # the one with the CA is still late
    assert result["with_ca"] == 1


def test_the_api_sends_the_numbers(client, business_with_filings, auth_headers, database):
    owner = database.session.get(User, business_with_filings.user_id)

    body = client.get(URL, headers=auth_headers(owner)).get_json()

    assert body["registered"] is True
    assert body["next_deadline"]["form_code"] in ("gstr_1", "gstr_3b", "itr")
    assert set(body) == {
        "message",
        "registered",
        "next_deadline",
        "due_this_month",
        "overdue",
        "with_ca",
    }


@pytest.mark.parametrize("role", [UserRole.CA, UserRole.ADMIN])
def test_other_roles_are_forbidden(client, make_user, auth_headers, role):
    response = client.get(URL, headers=auth_headers(make_user(role=role)))

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "FORBIDDEN"


def test_requires_login(client, database):
    response = client.get(URL)

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "AUTH_REQUIRED"
