"""The filing page: detail (CO5), path (CO8), checklist + status (CO7, CO10), mark filed (CO9),
undo and the acknowledgement file, and the list filters (CO4).

Uses the `business_with_filings` fixture (QRMP GSTR-1 / GSTR-3B + ITR). "Today" is fixed to
28 Sep 2026: Q1 filings are overdue, GSTR-1 for Q2 is due on 13 Oct 2026.
"""

import io
import uuid
from datetime import date

import pytest

from app import compliance as compliance_service, documents as documents_service
from app.models import Business, ComplianceItem, ComplianceStatus, EntityType, User, UserRole

ITEMS = "/api/v1/compliance/items"
PDF = b"%PDF-1.4 acknowledgement"


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(compliance_service, "today_in_india", lambda: date(2026, 9, 28))


@pytest.fixture()
def owner(business_with_filings, database, auth_headers):
    """The business owner's auth headers."""
    return auth_headers(database.session.get(User, business_with_filings.user_id))


def filing_id(database, form_code="gstr_1", period_label="Q2 2026-27"):
    return str(
        database.session.query(ComplianceItem)
        .filter_by(form_code=form_code, period_label=period_label)
        .one()
        .id
    )


def required_keys(client, headers, form_code="gstr_1"):
    checklist = client.get("/api/v1/compliance/forms/" + form_code, headers=headers).get_json()
    return [entry["key"] for entry in checklist["checklist"] if entry["required"]]


def tick(client, headers, item_id, key, ticked=True):
    return client.post(
        f"{ITEMS}/{item_id}/checklist", json={"key": key, "ticked": ticked}, headers=headers
    )


def mark_filed(client, headers, item_id, arn=None, file=None):
    data = {}
    if arn is not None:
        data["acknowledgement_no"] = arn
    if file is not None:
        data["file"] = file
    return client.post(
        f"{ITEMS}/{item_id}/mark-filed",
        data=data,
        headers=headers,
        content_type="multipart/form-data",
    )


# --- Detail (CO5) ----------------------------------------------------------------------


def test_detail_has_everything_the_page_shows(client, owner, database):
    body = client.get(f"{ITEMS}/{filing_id(database)}", headers=owner).get_json()

    assert body["filing"]["period_label"] == "Q2 2026-27"
    assert body["filing"]["due_date"] == "2026-10-13"
    assert body["filing"]["status"] == "upcoming"
    assert body["form_name"] == "GSTR-1 (quarterly, QRMP)"
    assert body["explanation"].startswith("# GSTR-1")
    assert body["instructions"]
    assert body["checklist"] and not any(entry["ticked"] for entry in body["checklist"])
    assert body["acknowledgement"] is None


def test_another_business_cannot_open_it(client, database, owner, make_user, auth_headers):
    stranger = make_user(role=UserRole.BUSINESS)
    database.session.add(
        Business(
            user_id=stranger.id,
            legal_name="Other Shop",
            entity_type=EntityType.INDIVIDUAL,
            state="Kerala",
            address="Kochi",
            description="Tailoring",
            annual_turnover=500_000,
            investment_amount=50_000,
            pan="PQRSX6789K",
            phone="9123456780",
            gst_registered=False,
            deducts_tds=False,
            pays_salary_above_limit=False,
        )
    )
    database.session.commit()

    response = client.get(f"{ITEMS}/{filing_id(database)}", headers=auth_headers(stranger))

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "FILING_NOT_FOUND"


def test_unknown_filing_is_404(client, owner):
    response = client.get(f"{ITEMS}/{uuid.uuid4()}", headers=owner)

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "FILING_NOT_FOUND"


def test_a_ca_cannot_use_the_business_pages(client, database, owner, make_user, auth_headers):
    ca = auth_headers(make_user(role=UserRole.CA))

    assert client.get(f"{ITEMS}/{filing_id(database)}", headers=ca).status_code == 403


# --- Path (CO8) ------------------------------------------------------------------------


def test_choose_a_path(client, owner, database):
    item_id = filing_id(database)

    body = client.post(f"{ITEMS}/{item_id}/path", json={"path": "self"}, headers=owner).get_json()
    assert body["filing"]["filing_path"] == "self"

    body = client.post(f"{ITEMS}/{item_id}/path", json={"path": "ca"}, headers=owner).get_json()
    assert body["filing"]["filing_path"] == "ca"


def test_path_is_locked_once_a_ca_has_it(client, owner, database):
    item_id = filing_id(database)
    database.session.get(ComplianceItem, uuid.UUID(item_id)).status = ComplianceStatus.WITH_CA
    database.session.commit()

    response = client.post(f"{ITEMS}/{item_id}/path", json={"path": "self"}, headers=owner)

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "FILING_LOCKED"


# --- Checklist and status (CO7, CO10) --------------------------------------------------


def test_ticking_moves_the_status_through_docs_pending_to_ready(client, owner, database):
    item_id = filing_id(database)
    keys = required_keys(client, owner)

    body = tick(client, owner, item_id, keys[0]).get_json()
    assert body["filing"]["status"] == "docs_pending"
    assert [entry["key"] for entry in body["checklist"] if entry["ticked"]] == [keys[0]]

    for key in keys[1:]:
        body = tick(client, owner, item_id, key).get_json()
    assert body["filing"]["status"] == "ready"

    for key in keys:
        body = tick(client, owner, item_id, key, ticked=False).get_json()
    assert body["filing"]["status"] == "upcoming"
    assert not any(entry["ticked"] for entry in body["checklist"])


def test_ticking_twice_keeps_one_tick(client, owner, database):
    item_id = filing_id(database)
    key = required_keys(client, owner)[0]

    tick(client, owner, item_id, key)
    body = tick(client, owner, item_id, key).get_json()

    assert [entry["key"] for entry in body["checklist"] if entry["ticked"]] == [key]


def test_a_late_filing_stays_overdue_when_ticked(client, owner, database):
    item_id = filing_id(database, period_label="Q1 2026-27")

    body = tick(client, owner, item_id, required_keys(client, owner)[0]).get_json()

    assert body["filing"]["status"] == "overdue"


def test_unknown_checklist_key_is_422(client, owner, database):
    response = tick(client, owner, filing_id(database), "no_such_document")

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "UNKNOWN_CHECKLIST_KEY"


# --- Mark filed, undo, acknowledgement (CO9) -------------------------------------------


def test_mark_filed_without_a_file(client, owner, database):
    body = mark_filed(client, owner, filing_id(database), arn=" aa270926123456x ").get_json()

    assert body["filing"]["status"] == "filed"
    assert body["filing"]["filing_path"] == "self"
    assert body["filing"]["filed_at"] is not None
    assert body["filing"]["acknowledgement_no"] == "AA270926123456X"
    assert body["acknowledgement"] is None


def test_an_overdue_filing_can_be_marked_filed(client, owner, database):
    body = mark_filed(client, owner, filing_id(database, period_label="Q1 2026-27")).get_json()

    assert body["filing"]["status"] == "filed"


def test_mark_filed_with_the_acknowledgement_and_download_it(client, owner, database):
    item_id = filing_id(database)

    body = mark_filed(
        client, owner, item_id, file=(io.BytesIO(PDF), "ack.pdf", "application/pdf")
    ).get_json()
    assert body["acknowledgement"]["filename"] == "ack.pdf"

    download = client.get(f"{ITEMS}/{item_id}/acknowledgement", headers=owner)
    assert download.status_code == 200
    assert download.data == PDF
    assert download.mimetype == "application/pdf"


def test_the_filing_page_does_not_open_the_acknowledgement_file(
    client, owner, database, monkeypatch
):
    item_id = filing_id(database)
    mark_filed(client, owner, item_id, file=(io.BytesIO(PDF), "ack.pdf", "application/pdf"))

    def file_unreadable(document_id):
        raise AssertionError("the page must not read the file")

    monkeypatch.setattr(documents_service, "read_document", file_unreadable)
    response = client.get(f"{ITEMS}/{item_id}", headers=owner)

    assert response.status_code == 200
    assert response.get_json()["acknowledgement"]["filename"] == "ack.pdf"
    assert "verified" in response.get_json()["acknowledgement"]["verification"]


def test_a_wrong_file_type_is_refused_and_nothing_changes(client, owner, database):
    item_id = filing_id(database)

    response = mark_filed(
        client, owner, item_id, file=(io.BytesIO(b"hello"), "a.txt", "text/plain")
    )

    assert response.status_code in (400, 415, 422)
    assert response.get_json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"
    assert (
        client.get(f"{ITEMS}/{item_id}", headers=owner).get_json()["filing"]["status"] == "upcoming"
    )


def test_cannot_mark_filed_twice_or_when_a_ca_has_it(client, owner, database):
    item_id = filing_id(database)
    mark_filed(client, owner, item_id)
    assert mark_filed(client, owner, item_id).get_json()["error"]["code"] == "ALREADY_FILED"

    other_id = filing_id(database, form_code="gstr_3b")
    database.session.get(ComplianceItem, uuid.UUID(other_id)).status = ComplianceStatus.WITH_CA
    database.session.commit()
    response = mark_filed(client, owner, other_id)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "FILING_WITH_CA"


def test_undo_mark_filed(client, owner, database):
    item_id = filing_id(database)
    key = required_keys(client, owner)[0]
    tick(client, owner, item_id, key)
    mark_filed(
        client, owner, item_id, arn="AA1", file=(io.BytesIO(PDF), "ack.pdf", "application/pdf")
    )

    body = client.post(f"{ITEMS}/{item_id}/unmark-filed", headers=owner).get_json()

    assert body["filing"]["status"] == "docs_pending"  # worked out again from the ticks
    assert body["filing"]["filed_at"] is None
    assert body["filing"]["acknowledgement_no"] is None
    assert body["acknowledgement"] is None
    assert client.get(f"{ITEMS}/{item_id}/acknowledgement", headers=owner).status_code == 404


def test_undo_needs_a_self_filed_filing(client, owner, database):
    response = client.post(f"{ITEMS}/{filing_id(database)}/unmark-filed", headers=owner)

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "NOT_SELF_FILED"


# --- List filters (CO4) ----------------------------------------------------------------


def test_list_filters(client, owner):
    def labels(query):
        items = client.get(ITEMS + query, headers=owner).get_json()
        return sorted((item["form_code"], item["period_label"]) for item in items)

    assert all(form == "gstr_1" for form, _ in labels("?form_code=gstr_1"))
    assert labels("?status=overdue") == [("gstr_1", "Q1 2026-27"), ("gstr_3b", "Q1 2026-27")]
    assert labels("?due_from=2026-10-01&due_to=2026-10-31") == [
        ("gstr_1", "Q2 2026-27"),
        ("gstr_3b", "Q2 2026-27"),
    ]
    assert client.get(ITEMS + "?status=nonsense", headers=owner).status_code == 422
