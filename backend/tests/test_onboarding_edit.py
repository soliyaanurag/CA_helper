"""Editing the business (PUT /onboarding/business), GSTIN checks and the state list."""

from datetime import date

import pytest

from app.models import Business, ComplianceItem
from app.models.enums import UserRole
from app.services import marketplace_service, onboarding_service
from app.utils.gstin import gstin_check_character
from tests.test_onboarding_register import FORM, URL, register

STATES_URL = "/api/v1/onboarding/states"


def synthetic_gstin(state_code: str, pan: str) -> str:
    """A made-up GSTIN with a valid check character (never a real one)."""
    first_14 = f"{state_code}{pan}1Z"
    return first_14 + gstin_check_character(first_14)


@pytest.fixture()
def owner(make_user, legal_rules, monkeypatch):
    monkeypatch.setattr(onboarding_service, "today_in_india", lambda: date(2026, 9, 27))
    return make_user(role=UserRole.BUSINESS)


@pytest.fixture()
def headers(owner, auth_headers):
    return auth_headers(owner)


def live_forms(database) -> dict:
    """{form code: number of live filings}."""
    counts = {}
    for item in database.session.query(ComplianceItem).filter(ComplianceItem.deleted_at.is_(None)):
        counts[item.form_code] = counts.get(item.form_code, 0) + 1
    return counts


# --- GSTIN and state checks ------------------------------------------------------------


def test_a_synthetic_gstin_passes(client, headers):
    gstin = synthetic_gstin("27", "ABCDE1234F")

    assert register(client, headers, gstin=gstin).status_code == 201


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"gstin": "27ABCDE1234F1Z5"}, "its last character does not match"),
        ({"state": "Gujarat"}, "the code of Gujarat is 24"),
        ({"pan": "ABCDE9999F"}, "does not match your PAN"),
    ],
    ids=["check character", "state code", "PAN"],
)
def test_a_gstin_must_fit_its_check_character_state_and_pan(client, headers, changes, message):
    response = register(client, headers, **changes)

    assert response.status_code == 422
    assert message in response.get_json()["error"]["details"]["json"]["gstin"][0]


def test_the_state_must_come_from_the_list(client, headers):
    response = register(client, headers, state="Maharastra")

    assert response.status_code == 422
    assert response.get_json()["error"]["details"]["json"]["state"] == [
        "Choose your state from the list."
    ]


def test_the_state_list_has_the_gst_codes(client, headers):
    states = client.get(STATES_URL, headers=headers).get_json()

    assert {"name": "Maharashtra", "code": "27"} in states
    assert len({state["code"] for state in states}) == len(states)


def test_a_state_typed_before_the_list_is_flagged(client, headers, database):
    register(client, headers)
    database.session.query(Business).update({"state": "maharashtra"})
    database.session.commit()

    business = client.get(URL, headers=headers).get_json()["business"]

    assert business["state_needs_review"] is True


# --- Editing ---------------------------------------------------------------------------


def test_editing_saves_the_business_and_reports_no_change(client, headers):
    register(client, headers)

    response = client.put(URL, json={**FORM, "legal_name": "Asha Traders LLP"}, headers=headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["business"]["legal_name"] == "Asha Traders LLP"
    assert body["changes"]["profile"] == []
    assert body["changes"]["filings"]["added"] == 0


def test_switching_to_monthly_returns_changes_the_profile_and_filings(client, headers, database):
    register(client, headers)
    assert live_forms(database)["gstr_3b"] == 4  # quarterly

    response = client.put(URL, json={**FORM, "gst_qrmp": False}, headers=headers)

    changes = response.get_json()["changes"]
    assert {"line": "gst_scheme", "old": "regular_qrmp", "new": "regular_monthly"} in changes[
        "profile"
    ]
    # Each quarter becomes the month it starts with (Q1 -> Apr ...); 8 more months each.
    assert changes["filings"]["moved"] == 8
    assert changes["filings"]["added"] == 16
    assert changes["filings"]["removed"] == 0
    assert live_forms(database)["gstr_3b"] == 12


def test_switching_back_to_quarterly_removes_the_extra_months(client, headers, database):
    register(client, headers, gst_qrmp=False)
    assert live_forms(database)["gstr_3b"] == 12

    response = client.put(URL, json=FORM, headers=headers)

    changes = response.get_json()["changes"]["filings"]
    assert (changes["moved"], changes["removed"]) == (8, 16)
    labels = {
        item.period_label
        for item in database.session.query(ComplianceItem).filter_by(form_code="gstr_3b")
        if item.deleted_at is None
    }
    assert labels == {"Q1 2026-27", "Q2 2026-27", "Q3 2026-27", "Q4 2026-27"}


def test_editing_keeps_filings_in_an_open_engagement(client, headers, database, monkeypatch):
    register(client, headers, gst_qrmp=False)
    may = database.session.query(ComplianceItem).filter_by(period_label="May 2026").first()
    monkeypatch.setattr(marketplace_service, "open_filing_ids", lambda ids: {may.id})

    response = client.put(URL, json=FORM, headers=headers)  # back to quarterly: no May

    assert response.get_json()["changes"]["filings"]["kept_with_ca"] == 1
    assert database.session.get(ComplianceItem, may.id).deleted_at is None


def test_editing_before_registering_is_404(client, headers):
    response = client.put(URL, json=FORM, headers=headers)

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "BUSINESS_NOT_FOUND"
