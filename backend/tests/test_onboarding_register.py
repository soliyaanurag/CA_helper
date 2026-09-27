"""POST/GET /api/v1/onboarding/business: registering a business (ON1) and reading it back."""

from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import ComplianceItem
from app.models.enums import UserRole
from app.services import onboarding_service

URL = "/api/v1/onboarding/business"

FORM = {
    "legal_name": "Asha Traders",
    "entity_type": "proprietorship",
    "state": "Maharashtra",
    "address": "12 Market Road, Pune",
    "description": "Retail shop selling household goods",
    "annual_turnover": "4500000.00",
    "investment_amount": "800000",
    "pan": "abcde1234f",  # lower case on purpose: it is stored in capitals
    "phone": "9876543210",
    "gst_registered": True,
    "gstin": "27ABCDE1234F1Z5",
    "deducts_tds": False,
    "pays_salary_above_limit": False,
}


@pytest.fixture()
def owner(make_user, legal_rules, monkeypatch):
    """A business user; "today" is fixed so the created filings are predictable."""
    monkeypatch.setattr(onboarding_service, "today_in_india", lambda: date(2026, 9, 27))
    return make_user(role=UserRole.BUSINESS)


def register(client, headers, **changes):
    return client.post(URL, json={**FORM, **changes}, headers=headers)


def test_register_returns_the_business_and_its_profile(client, owner, auth_headers):
    response = register(client, auth_headers(owner))

    assert response.status_code == 201
    body = response.get_json()
    assert body["business"]["legal_name"] == "Asha Traders"
    assert body["business"]["pan"] == "ABCDE1234F"
    assert body["business"]["annual_turnover"] == "4500000.00"
    assert body["profile"]["msme_tier"] == "micro"
    assert body["profile"]["gst_scheme"] == "regular_qrmp"
    assert body["profile"]["itr_form"] == "itr_4"
    assert body["profile"]["explanations"]["gst_scheme"]


def test_register_creates_the_filings(client, owner, auth_headers, database):
    register(client, auth_headers(owner))

    forms = {item.form_code for item in database.session.query(ComplianceItem)}
    assert forms == {"itr", "gstr_1", "gstr_3b"}


def test_pan_is_stored_encrypted(client, owner, auth_headers, database):
    register(client, auth_headers(owner))

    stored = database.session.execute(text("SELECT pan FROM businesses")).scalar_one()
    assert "ABCDE1234F" not in stored


def test_only_one_business_per_user(client, owner, auth_headers):
    register(client, auth_headers(owner))
    response = register(client, auth_headers(owner))

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "BUSINESS_EXISTS"


def test_unique_index_race_still_returns_business_exists(client, owner, auth_headers, monkeypatch):
    unique_violation = SimpleNamespace(diag=SimpleNamespace(constraint_name="ux_businesses_user_id"))

    def fail_commit():
        raise IntegrityError("INSERT INTO businesses ...", None, unique_violation)

    monkeypatch.setattr(onboarding_service.db.session, "commit", fail_commit)

    response = register(client, auth_headers(owner))

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "BUSINESS_EXISTS"


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"gstin": None}, "gstin"),  # GST registered without a GSTIN
        ({"deducts_tds": True}, "tan"),  # deducts TDS without a TAN
        ({"entity_type": "llp"}, "cin_llpin"),  # LLP without an LLPIN
        ({"gst_registered": False, "gstin": None, "gst_composition": True}, "gst_composition"),
        ({"pan": "12345"}, "pan"),
        ({"phone": "12345"}, "phone"),
        ({"annual_turnover": "-1"}, "annual_turnover"),
    ],
)
def test_invalid_forms_are_rejected(client, owner, auth_headers, changes, field):
    response = register(client, auth_headers(owner), **changes)

    assert response.status_code == 422
    assert field in response.get_json()["error"]["details"]["json"]


def test_unused_codes_are_dropped(client, owner, auth_headers):
    body = register(client, auth_headers(owner), gst_registered=False).get_json()

    assert body["business"]["gstin"] is None
    assert body["profile"]["gst_scheme"] == "not_registered"


def test_get_before_registering_is_404(client, owner, auth_headers):
    response = client.get(URL, headers=auth_headers(owner))

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "BUSINESS_NOT_FOUND"


def test_get_returns_the_saved_business(client, owner, auth_headers):
    register(client, auth_headers(owner))

    body = client.get(URL, headers=auth_headers(owner)).get_json()

    assert body["business"]["gstin"] == "27ABCDE1234F1Z5"
    assert body["profile"]["msme_tier"] == "micro"


@pytest.mark.parametrize("role", [UserRole.CA, UserRole.ADMIN])
def test_other_roles_are_forbidden(client, make_user, auth_headers, role):
    response = register(client, auth_headers(make_user(role=role)))

    assert response.status_code == 403


def test_requires_login(client, database):
    assert client.post(URL, json=FORM).status_code == 401
