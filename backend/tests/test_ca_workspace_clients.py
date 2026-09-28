"""The CA workspace: my clients with urgency (CW2, CW6), a client's workspace (CW3),
document requests (CW4), the CA marking a filing filed (CW5) and the batch view (CW7).

Uses the `business_with_filings` fixture (QRMP GSTR-1 / GSTR-3B + ITR). "Today" is fixed to
28 Sep 2026: Q1 filings are overdue, GSTR-1 for Q2 is due on 13 Oct 2026.
"""

import io
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models import (
    Business,
    CaProfile,
    CatalogService,
    ComplianceItem,
    ComplianceItemDocument,
    Document,
    DocumentRequest,
    Engagement,
    EngagementItem,
    Notification,
    ObligationTemplate,
    User,
)
from app.models.compliance import ComplianceStatus, FilingPath
from app.models.enums import UserRole
from app.models.marketplace import CaVerificationStatus, EngagementStatus
from app.seed import seed_service_catalog
from app.services import ca_workspace_service, compliance_service

BASE = "/api/v1/ca-workspace"
TODAY = date(2026, 9, 28)
PDF = b"%PDF-1.4 acknowledgement"


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(compliance_service, "today_in_india", lambda: TODAY)
    monkeypatch.setattr(ca_workspace_service, "today_in_india", lambda: TODAY)


def filing(database, form_code="gstr_1", period_label="Q2 2026-27") -> ComplianceItem:
    return (
        database.session.query(ComplianceItem)
        .filter_by(form_code=form_code, period_label=period_label)
        .one()
    )


_numbers = iter(range(200000, 999999))


def make_ca(make_user, database, name="Meera Shah"):
    user = make_user(role=UserRole.CA, full_name=name)
    profile = CaProfile(
        user_id=user.id,
        membership_no=str(next(_numbers)),
        cop_number="COP-1",
        city="Pune",
        languages=["english"],
        specializations=["gstr_1"],
        capacity=10,
        years_experience=5,
        verification_status=CaVerificationStatus.VERIFIED,
    )
    database.session.add(profile)
    database.session.commit()
    return user, profile


def engage(database, business, profile, items, status=EngagementStatus.ACTIVE) -> Engagement:
    """An engagement of the CA on these filings; active ones are "With CA"."""
    seed_service_catalog()
    engagement = Engagement(business_id=business.id, ca_profile_id=profile.id, status=status)
    database.session.add(engagement)
    database.session.flush()
    service = database.session.query(CatalogService).filter_by(code="gstr_1").one()
    for item in items:
        database.session.add(
            EngagementItem(
                engagement_id=engagement.id,
                compliance_item_id=item.id,
                service_id=service.id,
                listed_price=Decimal("600"),
            )
        )
        if status == EngagementStatus.ACTIVE:
            item.status = ComplianceStatus.WITH_CA
            item.filing_path = FilingPath.CA
    database.session.commit()
    return engagement


@pytest.fixture()
def work(business_with_filings, database, make_user, auth_headers):
    """The CA works on GSTR-1 Q1 (overdue) and Q2 (due 13 Oct) of the fixture business."""
    ca_user, profile = make_ca(make_user, database)
    q1, q2 = filing(database, period_label="Q1 2026-27"), filing(database)
    engagement = engage(database, business_with_filings, profile, [q1, q2])
    owner = database.session.get(User, business_with_filings.user_id)
    return {
        "business": business_with_filings,
        "owner": owner,
        "owner_headers": auth_headers(owner),
        "ca_user": ca_user,
        "ca": profile,
        "ca_headers": auth_headers(ca_user),
        "engagement": engagement,
        "q1": q1,
        "q2": q2,
    }


def ask(client, w, item=None, key="sales_invoices", message="Please upload the sales invoices"):
    return client.post(
        f"{BASE}/clients/{w['business'].id}/document-requests",
        json={
            "compliance_item_id": str((item or w["q2"]).id),
            "checklist_key": key,
            "message": message,
        },
        headers=w["ca_headers"],
    )


def upload(client, headers, name="invoices.pdf"):
    form = {"doc_type": "invoice", "file": (io.BytesIO(PDF), name, "application/pdf")}
    return client.post(
        "/api/v1/documents", data=form, headers=headers, content_type="multipart/form-data"
    )


def ca_mark_filed(client, w, item, arn=None, file=None):
    data = {}
    if arn:
        data["acknowledgement_no"] = arn
    if file:
        data["file"] = file
    return client.post(
        f"{BASE}/clients/{w['business'].id}/filings/{item.id}/mark-filed",
        data=data,
        headers=w["ca_headers"],
        content_type="multipart/form-data",
    )


# --- My clients and urgency (CW2, CW6) ---------------------------------------------------


def test_my_clients_with_urgency_and_why(client, work):
    response = client.get(f"{BASE}/clients", headers=work["ca_headers"])

    assert response.status_code == 200
    [row] = response.get_json()
    assert row["business_name"] == "Asha Traders"
    assert (row["filing_count"], row["open_filing_count"], row["overdue_count"]) == (2, 2, 1)
    assert row["next_deadline"] == "2026-10-13"
    assert row["missing_documents"] == 8  # 4 required GSTR-1 documents x 2 filings
    reasons = {reason["reason"]: reason["points"] for reason in row["reasons"]}
    assert reasons == {
        "1 filing(s) overdue": ca_workspace_service.POINTS_PER_OVERDUE_FILING,
        "8 required document(s) not ready": 8 * ca_workspace_service.POINTS_PER_MISSING_DOCUMENT,
    }
    assert row["score"] == sum(reasons.values())


def test_urgency_counts_near_deadlines_and_open_requests(monkeypatch):
    # Filings with nothing missing, due in 3, 6 and 34 days.
    monkeypatch.setattr(compliance_service, "checklist_progress", lambda filing: {"missing": []})

    def due(day):
        return SimpleNamespace(due_date=day)

    soon = ca_workspace_service._urgency([due(date(2026, 10, 1))], 2, None, TODAY)
    week = ca_workspace_service._urgency([due(date(2026, 10, 4))], 0, None, TODAY)
    later = ca_workspace_service._urgency([due(date(2026, 11, 1))], 0, None, TODAY)

    assert soon["reasons"] == [
        {"reason": "Next deadline in 3 day(s)", "points": 25},
        {"reason": "2 document request(s) not answered", "points": 6},
    ]
    assert week["reasons"] == [{"reason": "Next deadline in 6 days", "points": 10}]
    assert later["score"] == 0 and later["reasons"] == []


def test_clients_are_sorted_most_urgent_first(client, work, database, make_user, auth_headers):
    from tests.test_documents_vault import other_business

    other_business(make_user, database, auth_headers)
    calm = database.session.query(Business).filter_by(legal_name="Other Co").one()
    template = database.session.get(ObligationTemplate, work["q2"].template_id)
    later = ComplianceItem(
        business_id=calm.id,
        template_id=template.id,
        form_code="gstr_1",
        fy="2026-27",
        period_label="Q3 2026-27",
        period_start=date(2026, 10, 1),
        period_end=date(2026, 12, 31),
        due_date=date(2027, 1, 13),
        status=ComplianceStatus.UPCOMING,
    )
    database.session.add(later)
    database.session.commit()
    engage(database, calm, work["ca"], [later])

    rows = client.get(f"{BASE}/clients", headers=work["ca_headers"]).get_json()

    assert [row["business_name"] for row in rows] == ["Asha Traders", "Other Co"]
    assert rows[0]["score"] > rows[1]["score"]


def test_only_active_engagements_are_clients(client, work, database, make_user, auth_headers):
    other_user, other_ca = make_ca(make_user, database, name="Other CA")
    engage(
        database,
        work["business"],
        other_ca,
        [filing(database, "gstr_3b")],
        EngagementStatus.REQUESTED,
    )

    assert client.get(f"{BASE}/clients", headers=auth_headers(other_user)).get_json() == []
    work["engagement"].status = EngagementStatus.COMPLETED
    database.session.commit()
    assert client.get(f"{BASE}/clients", headers=work["ca_headers"]).get_json() == []


def test_workspace_routes_are_for_cas(client, work, make_user, auth_headers):
    no_profile = auth_headers(make_user(role=UserRole.CA))

    assert client.get(f"{BASE}/clients").status_code == 401
    assert client.get(f"{BASE}/clients", headers=work["owner_headers"]).status_code == 403
    response = client.get(f"{BASE}/clients", headers=no_profile)
    assert response.get_json()["error"]["code"] == "CA_PROFILE_NOT_FOUND"


# --- A client's workspace (CW3) ----------------------------------------------------------


def test_client_workspace_shows_profile_and_only_engaged_filings(client, work, database):
    document = upload(client, work["owner_headers"]).get_json()
    client.post(
        f"/api/v1/documents/{document['id']}/links",
        json={"compliance_item_id": str(work["q2"].id), "checklist_key": "sales_invoices"},
        headers=work["owner_headers"],
    )

    response = client.get(f"{BASE}/clients/{work['business'].id}", headers=work["ca_headers"])

    body = response.get_json()
    assert response.status_code == 200
    assert body["business"]["legal_name"] == "Asha Traders"
    assert body["business"]["pan"] == "ABCDE1234F"  # the full profile during active work
    assert "profile" in body
    assert [row["filing"]["period_label"] for row in body["filings"]] == [
        "Q1 2026-27",
        "Q2 2026-27",
    ]
    q2 = body["filings"][1]
    assert q2["filing"]["status"] == "with_ca"
    assert [entry["key"] for entry in q2["checklist"] if entry["ticked"]] == ["sales_invoices"]
    assert q2["documents"][0]["original_filename"] == "invoices.pdf"
    assert q2["documents"][0]["checklist_key"] == "sales_invoices"


def test_no_workspace_without_active_work(client, work, database, make_user, auth_headers):
    other_user, other_ca = make_ca(make_user, database, name="Other CA")
    engage(
        database,
        work["business"],
        other_ca,
        [filing(database, "gstr_3b")],
        EngagementStatus.REQUESTED,
    )
    url = f"{BASE}/clients/{work['business'].id}"

    response = client.get(url, headers=auth_headers(other_user))
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "BUSINESS_NOT_FOUND"
    work["engagement"].status = EngagementStatus.COMPLETED
    database.session.commit()
    assert client.get(url, headers=work["ca_headers"]).status_code == 404


# --- Document requests (CW4) -------------------------------------------------------------


def test_ca_asks_for_a_document_and_the_business_sees_a_to_do(client, work, database, mailbox):
    response = ask(client, work)

    assert response.status_code == 201
    assert response.get_json()["status"] == "open"
    note = database.session.query(Notification).filter_by(user_id=work["owner"].id).one()
    assert note.type == "document_request"
    assert note.link == f"/business/compliance/{work['q2'].id}"
    assert [message["To"] for message in mailbox] == [work["owner"].email]
    to_dos = client.get(f"{BASE}/document-requests", headers=work["owner_headers"]).get_json()
    assert to_dos[0]["message"] == "Please upload the sales invoices"
    assert to_dos[0]["ca_name"] == "Meera Shah"
    assert to_dos[0]["form_code"] == "gstr_1"
    by_filing = client.get(
        f"{BASE}/document-requests?compliance_item_id={work['q1'].id}",
        headers=work["owner_headers"],
    ).get_json()
    assert by_filing == []
    workspace = client.get(f"{BASE}/clients/{work['business'].id}", headers=work["ca_headers"])
    assert len(workspace.get_json()["filings"][1]["open_requests"]) == 1
    clients = client.get(f"{BASE}/clients", headers=work["ca_headers"]).get_json()
    assert clients[0]["open_request_count"] == 1


def test_document_request_checks(client, work, database):
    not_engaged = filing(database, "gstr_3b")

    assert ask(client, work, item=not_engaged).get_json()["error"]["code"] == "FILING_NOT_FOUND"
    assert ask(client, work, key="nope").get_json()["error"]["code"] == "UNKNOWN_CHECKLIST_KEY"
    assert ask(client, work, message="   ").status_code == 422
    assert ask(client, work, key="general").status_code == 201


def test_ca_cancels_a_request(client, work, database):
    request_id = ask(client, work).get_json()["id"]

    response = client.post(
        f"{BASE}/document-requests/{request_id}/cancel", headers=work["ca_headers"]
    )
    again = client.post(f"{BASE}/document-requests/{request_id}/cancel", headers=work["ca_headers"])

    assert response.get_json()["status"] == "cancelled"
    assert again.get_json()["error"]["code"] == "REQUEST_NOT_OPEN"
    assert client.get(f"{BASE}/document-requests", headers=work["owner_headers"]).get_json() == []


def test_business_fulfils_a_request_with_a_file(client, work, database, mailbox):
    request_id = ask(client, work).get_json()["id"]
    document = upload(client, work["owner_headers"]).get_json()
    mailbox.clear()

    response = client.post(
        f"{BASE}/document-requests/{request_id}/fulfil",
        json={"document_id": document["id"]},
        headers=work["owner_headers"],
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "fulfilled"
    link = database.session.query(ComplianceItemDocument).one()
    assert (link.compliance_item_id, link.checklist_key) == (work["q2"].id, "sales_invoices")
    assert [message["To"] for message in mailbox] == [work["ca_user"].email]
    ca_note = database.session.query(Notification).filter_by(user_id=work["ca_user"].id).one()
    assert ca_note.link == f"/ca/clients/{work['business'].id}"
    # The CA can now open the file (it serves a filing of the active engagement).
    opened = client.get(f"/api/v1/documents/{document['id']}/file", headers=work["ca_headers"])
    assert opened.status_code == 200
    again = client.post(
        f"{BASE}/document-requests/{request_id}/fulfil",
        json={"document_id": document["id"]},
        headers=work["owner_headers"],
    )
    assert again.get_json()["error"]["code"] == "REQUEST_NOT_OPEN"


def test_another_business_cannot_fulfil(client, work, database, make_user, auth_headers):
    from tests.test_documents_vault import other_business

    request_id = ask(client, work).get_json()["id"]
    other = other_business(make_user, database, auth_headers)
    theirs = upload(client, other).get_json()

    response = client.post(
        f"{BASE}/document-requests/{request_id}/fulfil",
        json={"document_id": theirs["id"]},
        headers=other,
    )

    assert response.get_json()["error"]["code"] == "REQUEST_NOT_FOUND"
    assert client.get(f"{BASE}/document-requests", headers=other).get_json() == []


# --- The CA marks a filing filed (CW5) ---------------------------------------------------


def test_ca_marks_one_filing_filed_with_the_acknowledgement(client, work, database, mailbox):
    request_id = ask(client, work).get_json()["id"]
    mailbox.clear()

    response = ca_mark_filed(
        client, work, work["q2"], arn="aa270926123456x", file=(io.BytesIO(PDF), "ack.pdf")
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body == {
        "compliance_item_id": str(work["q2"].id),
        "status": "filed",
        "acknowledgement_no": "AA270926123456X",
        "engagement_completed": False,
    }
    database.session.expire_all()
    q2 = database.session.get(ComplianceItem, work["q2"].id)
    assert q2.filing_path == FilingPath.CA
    document = database.session.get(Document, q2.acknowledgement_document_id)
    assert document.owner_id == work["owner"].id
    assert document.uploaded_by_id == work["ca_user"].id
    assert database.session.get(DocumentRequest, request_id).status == "cancelled"
    assert [message["To"] for message in mailbox] == [work["owner"].email]
    # The business sees it on its filing page, with the acknowledgement.
    page = client.get(f"/api/v1/compliance/items/{q2.id}", headers=work["owner_headers"])
    assert page.get_json()["acknowledgement"]["filename"] == "ack.pdf"
    ack = client.get(
        f"/api/v1/compliance/items/{q2.id}/acknowledgement", headers=work["owner_headers"]
    )
    assert ack.data == PDF
    # The business cannot undo a filing its CA marked.
    undo = client.post(
        f"/api/v1/compliance/items/{q2.id}/unmark-filed", headers=work["owner_headers"]
    )
    assert undo.get_json()["error"]["code"] == "NOT_SELF_FILED"


def test_the_last_filing_completes_the_engagement(client, work, database):
    ca_mark_filed(client, work, work["q1"])
    response = ca_mark_filed(client, work, work["q2"])

    assert response.get_json()["engagement_completed"] is True
    database.session.expire_all()
    assert database.session.get(Engagement, work["engagement"].id).status == "completed"
    # Access ends with the engagement.
    workspace = client.get(f"{BASE}/clients/{work['business'].id}", headers=work["ca_headers"])
    assert workspace.status_code == 404


def test_ca_mark_filed_checks(client, work, database):
    assert ca_mark_filed(client, work, filing(database, "gstr_3b")).status_code == 404
    ca_mark_filed(client, work, work["q2"])
    again = ca_mark_filed(client, work, work["q2"])
    assert again.get_json()["error"]["code"] == "ALREADY_FILED"
    wrong_type = ca_mark_filed(client, work, work["q1"], file=(io.BytesIO(b"text"), "a.pdf"))
    assert wrong_type.get_json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"
    database.session.expire_all()
    assert database.session.get(ComplianceItem, work["q1"].id).status == "with_ca"


# --- Batch view (CW7) --------------------------------------------------------------------


def test_batches_group_by_form_and_due_date(client, work):
    document = upload(client, work["owner_headers"]).get_json()
    for key in compliance_service.checklist_keys("gstr_1"):
        client.post(
            f"/api/v1/documents/{document['id']}/links",
            json={"compliance_item_id": str(work["q2"].id), "checklist_key": key},
            headers=work["owner_headers"],
        )

    batches = client.get(f"{BASE}/batches", headers=work["ca_headers"]).get_json()

    assert [(batch["form_code"], batch["due_date"]) for batch in batches] == [
        ("gstr_1", work["q1"].due_date.isoformat()),
        ("gstr_1", "2026-10-13"),
    ]
    q1_row = batches[0]["filings"][0]
    assert q1_row["ready"] is False and len(q1_row["missing"]) == 4
    assert batches[1]["ready_count"] == 1
    assert batches[1]["filings"][0]["business_name"] == "Asha Traders"
    ca_mark_filed(client, work, work["q2"])
    assert len(client.get(f"{BASE}/batches", headers=work["ca_headers"]).get_json()) == 1
