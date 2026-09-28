"""The document vault: upload (DO2), list and filters (DO3), download (DO4), delete (DO5),
links to filings (DO6) and who may open a file (DO7).

Uses the `business_with_filings` fixture (QRMP GSTR-1 / GSTR-3B + ITR). "Today" is fixed to
28 Sep 2026: Q1 filings are overdue, GSTR-1 for Q2 is due on 13 Oct 2026.
"""

import io
from datetime import date
from decimal import Decimal

import pytest

from app.models import (
    Business,
    CaProfile,
    CatalogService,
    ComplianceItem,
    ComplianceItemDocument,
    Document,
    Engagement,
    EngagementItem,
    User,
)
from app.models.compliance import ComplianceStatus
from app.models.enums import UserRole
from app.models.marketplace import CaVerificationStatus, EngagementStatus
from app.models.onboarding import EntityType
from app.seed import seed_service_catalog
from app.services import compliance_service, documents_service

DOCS = "/api/v1/documents"
ITEMS = "/api/v1/compliance/items"
PDF = b"%PDF-1.4 sales register"


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(compliance_service, "today_in_india", lambda: date(2026, 9, 28))


@pytest.fixture()
def owner(business_with_filings, database, auth_headers):
    """The business owner's auth headers."""
    return auth_headers(database.session.get(User, business_with_filings.user_id))


def filing(database, form_code="gstr_1", period_label="Q2 2026-27") -> ComplianceItem:
    return (
        database.session.query(ComplianceItem)
        .filter_by(form_code=form_code, period_label=period_label)
        .one()
    )


def upload(client, headers, name="sales.pdf", data=PDF, doc_type="sales_register", **fields):
    form = {"doc_type": doc_type, "file": (io.BytesIO(data), name, "application/pdf")}
    for key, value in fields.items():
        form[key] = str(value)
    return client.post(DOCS, data=form, headers=headers, content_type="multipart/form-data")


def link(client, headers, document_id, item_id, key="general"):
    return client.post(
        f"{DOCS}/{document_id}/links",
        json={"compliance_item_id": str(item_id), "checklist_key": key},
        headers=headers,
    )


def other_business(make_user, database, auth_headers):
    """A second registered business, with its own headers."""
    user = make_user(role=UserRole.BUSINESS)
    database.session.add(
        Business(
            user_id=user.id,
            legal_name="Other Co",
            entity_type=EntityType.PROPRIETORSHIP,
            state="Kerala",
            address="Kochi",
            description="Shop",
            annual_turnover=100_000,
            investment_amount=10_000,
            pan="ZZZZZ9999Z",
            phone="9000000000",
            gst_registered=False,
            deducts_tds=False,
            pays_salary_above_limit=False,
        )
    )
    database.session.commit()
    return auth_headers(user)


def make_ca(make_user, database):
    """A verified CA (user, profile)."""
    user = make_user(role=UserRole.CA, full_name="Meera Shah")
    profile = CaProfile(
        user_id=user.id,
        membership_no="123456",
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


def engage(database, business, profile, item, status=EngagementStatus.ACTIVE) -> Engagement:
    """An engagement of the CA on one filing."""
    seed_service_catalog()
    engagement = Engagement(business_id=business.id, ca_profile_id=profile.id, status=status)
    database.session.add(engagement)
    database.session.flush()
    service = database.session.query(CatalogService).filter_by(code="gstr_1").one()
    database.session.add(
        EngagementItem(
            engagement_id=engagement.id,
            compliance_item_id=item.id,
            service_id=service.id,
            listed_price=Decimal("600"),
        )
    )
    database.session.commit()
    return engagement


# --- Upload (DO2) and the list (DO3) ---------------------------------------------------


def test_upload_to_the_vault(client, owner, database, business_with_filings):
    response = upload(client, owner, fy="2026-27", period_label=" Apr 2026 ")

    assert response.status_code == 201
    body = response.get_json()
    assert body["doc_type"] == "sales_register"
    assert body["original_filename"] == "sales.pdf"
    assert body["size_bytes"] == len(PDF)
    assert body["fy"] == "2026-27"
    assert body["period_label"] == "Apr 2026"
    assert body["ocr_status"] == "none"
    assert body["links"] == [] and body["acknowledgement_of"] == []
    document = database.session.get(Document, body["id"])
    assert document.owner_id == business_with_filings.user_id
    assert document.uploaded_by_id == business_with_filings.user_id


def test_every_upload_calls_the_ocr_hook(client, owner, monkeypatch):
    seen = []
    monkeypatch.setattr(documents_service, "on_document_uploaded", seen.append)

    upload(client, owner)

    assert len(seen) == 1 and seen[0].id is not None


@pytest.mark.parametrize(
    ("fields", "field"),
    [
        ({"doc_type": "certificate_of_practice"}, "doc_type"),
        ({"doc_type": "passport"}, "doc_type"),
        ({"fy": "2026-28"}, "fy"),
        ({"fy": "26-27"}, "fy"),
    ],
)
def test_upload_checks_its_fields(client, owner, database, fields, field):
    response = upload(client, owner, **fields)

    assert response.status_code == 422
    assert field in response.get_json()["error"]["details"]["form"]
    assert database.session.query(Document).count() == 0


def test_upload_refuses_a_file_that_is_not_a_pdf_jpg_or_png(client, owner, database):
    response = upload(client, owner, name="notes.pdf", data=b"hello")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"
    assert database.session.query(Document).count() == 0


def test_the_vault_needs_a_registered_business(client, make_user, auth_headers):
    headers = auth_headers(make_user(role=UserRole.BUSINESS))

    assert client.get(DOCS, headers=headers).get_json()["error"]["code"] == "BUSINESS_NOT_FOUND"
    assert upload(client, headers).status_code == 404


def test_list_is_newest_first_filtered_and_paginated(client, owner, database):
    upload(client, owner, name="a.pdf", fy="2025-26")
    upload(client, owner, name="b.pdf", fy="2026-27", doc_type="bank_statement")
    upload(client, owner, name="c.pdf", fy="2026-27")

    everything = client.get(DOCS, headers=owner).get_json()
    assert [row["original_filename"] for row in everything["items"]] == ["c.pdf", "b.pdf", "a.pdf"]
    assert everything["total"] == 3

    def names(query):
        body = client.get(DOCS + "?" + query, headers=owner).get_json()
        return [row["original_filename"] for row in body["items"]]

    assert names("fy=2026-27") == ["c.pdf", "b.pdf"]
    assert names("doc_type=bank_statement") == ["b.pdf"]
    assert names("fy=2026-27&doc_type=sales_register") == ["c.pdf"]
    assert names("page=2&page_size=2") == ["a.pdf"]
    assert client.get(DOCS + "?fy=2026", headers=owner).status_code == 422


def test_list_by_filing_has_its_documents_and_acknowledgement(client, owner, database):
    q2 = filing(database)
    linked = upload(client, owner, name="linked.pdf").get_json()
    link(client, owner, linked["id"], q2.id)
    upload(client, owner, name="unlinked.pdf")
    q1 = filing(database, period_label="Q1 2026-27")
    client.post(
        f"{ITEMS}/{q1.id}/mark-filed",
        data={"file": (io.BytesIO(b"%PDF-1.4 ack"), "ack.pdf", "application/pdf")},
        headers=owner,
        content_type="multipart/form-data",
    )

    by_q2 = client.get(f"{DOCS}?compliance_item_id={q2.id}", headers=owner).get_json()["items"]
    by_q1 = client.get(f"{DOCS}?compliance_item_id={q1.id}", headers=owner).get_json()["items"]

    assert [row["original_filename"] for row in by_q2] == ["linked.pdf"]
    assert by_q2[0]["links"][0]["form_code"] == "gstr_1"
    assert by_q2[0]["links"][0]["period_label"] == "Q2 2026-27"
    assert [row["original_filename"] for row in by_q1] == ["ack.pdf"]
    assert by_q1[0]["doc_type"] == "acknowledgement"
    assert by_q1[0]["acknowledgement_of"] == [
        {"compliance_item_id": str(q1.id), "form_code": "gstr_1", "period_label": "Q1 2026-27"}
    ]


def test_a_business_sees_only_its_own_documents(client, owner, database, make_user, auth_headers):
    mine = upload(client, owner).get_json()
    other = other_business(make_user, database, auth_headers)

    assert client.get(DOCS, headers=other).get_json()["items"] == []
    assert client.get(f"{DOCS}/{mine['id']}/file", headers=other).status_code == 404
    assert client.delete(f"{DOCS}/{mine['id']}", headers=other).status_code == 404
    assert link(client, other, mine["id"], filing(database).id).status_code == 404


# --- Download (DO4) --------------------------------------------------------------------


def test_the_owner_downloads_the_decrypted_file(client, owner, upload_dir):
    document = upload(client, owner, name="sales.pdf").get_json()

    response = client.get(f"{DOCS}/{document['id']}/file", headers=owner)

    assert response.status_code == 200
    assert response.data == PDF
    assert response.mimetype == "application/pdf"
    assert "sales.pdf" in response.headers["Content-Disposition"]
    stored = next(upload_dir.iterdir()).read_bytes()
    assert PDF not in stored  # encrypted at rest


def test_unknown_or_deleted_document_is_404(client, owner):
    document = upload(client, owner).get_json()
    client.delete(f"{DOCS}/{document['id']}", headers=owner)

    for document_id in [document["id"], "00000000-0000-0000-0000-000000000000"]:
        response = client.get(f"{DOCS}/{document_id}/file", headers=owner)
        assert response.status_code == 404
        assert response.get_json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


# --- Who may open a file (DO7) ---------------------------------------------------------


def test_a_ca_opens_only_documents_of_filings_in_active_work(
    client, owner, database, business_with_filings, make_user, auth_headers
):
    q2 = filing(database)
    linked = upload(client, owner, name="linked.pdf").get_json()
    link(client, owner, linked["id"], q2.id, "sales_invoices")
    other_filing = upload(client, owner, name="other-filing.pdf").get_json()
    link(client, owner, other_filing["id"], filing(database, "gstr_3b"), "general")
    unlinked = upload(client, owner, name="unlinked.pdf").get_json()
    ca_user, profile = make_ca(make_user, database)
    ca = auth_headers(ca_user)

    def status(document):
        return client.get(f"{DOCS}/{document['id']}/file", headers=ca).status_code

    # Only a request so far: no documents.
    engagement = engage(
        database, business_with_filings, profile, q2, status=EngagementStatus.REQUESTED
    )
    assert status(linked) == 404

    engagement.status = EngagementStatus.ACTIVE
    database.session.commit()
    assert status(linked) == 200
    assert client.get(f"{DOCS}/{linked['id']}/file", headers=ca).data == PDF
    assert status(other_filing) == 404
    assert status(unlinked) == 404

    engagement.status = EngagementStatus.COMPLETED
    database.session.commit()
    assert status(linked) == 404


def test_a_ca_opens_the_acknowledgement_of_an_engaged_filing(
    client, owner, database, business_with_filings, make_user, auth_headers
):
    q2 = filing(database)
    ca_user, profile = make_ca(make_user, database)
    engage(database, business_with_filings, profile, q2)
    # The business marks it filed with an acknowledgement (as a CA will in PR 3).
    q2.status = ComplianceStatus.READY
    database.session.commit()
    client.post(
        f"{ITEMS}/{q2.id}/mark-filed",
        data={"file": (io.BytesIO(b"%PDF-1.4 ack"), "ack.pdf", "application/pdf")},
        headers=owner,
        content_type="multipart/form-data",
    )
    acknowledgement_id = database.session.get(ComplianceItem, q2.id).acknowledgement_document_id

    response = client.get(f"{DOCS}/{acknowledgement_id}/file", headers=auth_headers(ca_user))

    assert response.status_code == 200


def test_a_ca_without_a_profile_opens_nothing(client, owner, make_user, auth_headers):
    document = upload(client, owner).get_json()
    ca = auth_headers(make_user(role=UserRole.CA))

    assert client.get(f"{DOCS}/{document['id']}/file", headers=ca).status_code == 404


def test_admins_never_read_document_contents(client, owner, make_user, auth_headers):
    document = upload(client, owner).get_json()
    admin = auth_headers(make_user(role=UserRole.ADMIN))

    assert client.get(f"{DOCS}/{document['id']}/file", headers=admin).status_code == 403
    assert client.get(DOCS, headers=admin).status_code == 403


def test_the_vault_is_for_businesses_only(client, owner, make_user, auth_headers):
    document = upload(client, owner).get_json()
    ca = auth_headers(make_user(role=UserRole.CA))

    assert client.get(DOCS).status_code == 401
    assert client.get(DOCS, headers=ca).status_code == 403
    assert upload(client, ca).status_code == 403
    assert client.delete(f"{DOCS}/{document['id']}", headers=ca).status_code == 403


# --- Links to filings (DO6) ------------------------------------------------------------


def test_link_to_a_checklist_entry_ticks_it(client, owner, database):
    q2 = filing(database)
    document = upload(client, owner).get_json()

    response = link(client, owner, document["id"], q2.id, "sales_invoices")

    assert response.status_code == 200
    assert response.get_json()["links"][0]["checklist_key"] == "sales_invoices"
    page = client.get(f"{ITEMS}/{q2.id}", headers=owner).get_json()
    ticked = [entry["key"] for entry in page["checklist"] if entry["ticked"]]
    assert ticked == ["sales_invoices"]
    assert page["filing"]["status"] == "docs_pending"


def test_general_link_ticks_nothing_and_linking_twice_keeps_one(client, owner, database):
    q2 = filing(database)
    document = upload(client, owner).get_json()

    link(client, owner, document["id"], q2.id)
    response = link(client, owner, document["id"], q2.id)

    assert len(response.get_json()["links"]) == 1
    assert database.session.query(ComplianceItemDocument).count() == 1
    assert database.session.get(ComplianceItem, q2.id).status == ComplianceStatus.UPCOMING


def test_one_file_serves_several_filings(client, owner, database):
    document = upload(client, owner).get_json()

    link(client, owner, document["id"], filing(database).id, "sales_invoices")
    response = link(client, owner, document["id"], filing(database, "gstr_3b").id)

    assert sorted(row["form_code"] for row in response.get_json()["links"]) == [
        "gstr_1",
        "gstr_3b",
    ]


def test_upload_and_link_in_one_request(client, owner, database):
    q2 = filing(database)

    response = upload(client, owner, compliance_item_id=q2.id, checklist_key="hsn_summary")

    body = response.get_json()
    assert response.status_code == 201
    assert body["links"][0]["checklist_key"] == "hsn_summary"
    assert body["fy"] == q2.fy and body["period_label"] == "Q2 2026-27"  # from the filing


def test_link_checks_the_key_and_the_filing(client, owner, database, make_user, auth_headers):
    q2 = filing(database)
    document = upload(client, owner).get_json()

    wrong_key = link(client, owner, document["id"], q2.id, "no_such_entry")
    assert wrong_key.status_code == 422
    assert wrong_key.get_json()["error"]["code"] == "UNKNOWN_CHECKLIST_KEY"
    # A wrong key in an upload stores nothing.
    assert upload(client, owner, compliance_item_id=q2.id, checklist_key="x").status_code == 422
    assert database.session.query(Document).count() == 1

    other = other_business(make_user, database, auth_headers)
    theirs = upload(client, other).get_json()
    response = link(client, other, theirs["id"], q2.id)
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "FILING_NOT_FOUND"


def test_unlink_removes_the_link_but_keeps_the_tick(client, owner, database):
    q2 = filing(database)
    document = upload(client, owner).get_json()
    link_id = link(client, owner, document["id"], q2.id, "sales_invoices").get_json()["links"][0][
        "id"
    ]

    assert client.delete(f"{DOCS}/links/{link_id}", headers=owner).status_code == 204

    assert database.session.query(ComplianceItemDocument).count() == 0
    page = client.get(f"{ITEMS}/{q2.id}", headers=owner).get_json()
    assert [entry["key"] for entry in page["checklist"] if entry["ticked"]] == ["sales_invoices"]
    assert client.delete(f"{DOCS}/links/{link_id}", headers=owner).status_code == 404


def test_a_filed_filings_documents_are_fixed(client, owner, database):
    q2 = filing(database)
    document = upload(client, owner).get_json()
    link_id = link(client, owner, document["id"], q2.id).get_json()["links"][0]["id"]
    q2.status = ComplianceStatus.FILED
    database.session.commit()
    another = upload(client, owner, name="late.pdf").get_json()

    for response in [
        link(client, owner, another["id"], q2.id),
        upload(client, owner, compliance_item_id=q2.id),
        client.delete(f"{DOCS}/links/{link_id}", headers=owner),
    ]:
        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "FILING_LOCKED"


def test_a_business_can_add_documents_while_its_ca_works(client, owner, database):
    q2 = filing(database)
    q2.status = ComplianceStatus.WITH_CA
    database.session.commit()

    response = upload(client, owner, compliance_item_id=q2.id, checklist_key="sales_invoices")

    assert response.status_code == 201
    assert database.session.get(ComplianceItem, q2.id).status == ComplianceStatus.WITH_CA


# --- Delete (DO5) ----------------------------------------------------------------------


def test_delete_is_soft_and_removes_open_links(client, owner, database):
    document = upload(client, owner).get_json()
    link(client, owner, document["id"], filing(database).id)

    assert client.delete(f"{DOCS}/{document['id']}", headers=owner).status_code == 204

    row = database.session.get(Document, document["id"])
    assert row.deleted_at is not None and row.is_active is False
    assert database.session.query(ComplianceItemDocument).count() == 0
    assert client.get(DOCS, headers=owner).get_json()["items"] == []


def test_proof_of_a_filed_filing_cannot_be_deleted(client, owner, database):
    q2 = filing(database)
    document = upload(client, owner).get_json()
    link(client, owner, document["id"], q2.id)
    q2.status = ComplianceStatus.FILED
    database.session.commit()

    response = client.delete(f"{DOCS}/{document['id']}", headers=owner)

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "DOCUMENT_IN_USE"
    assert "GSTR-1 (Q2 2026-27)" in response.get_json()["error"]["message"]
    assert database.session.get(Document, document["id"]).deleted_at is None


def test_an_acknowledgement_cannot_be_deleted_from_the_vault(client, owner, database):
    q1 = filing(database, period_label="Q1 2026-27")
    client.post(
        f"{ITEMS}/{q1.id}/mark-filed",
        data={"file": (io.BytesIO(b"%PDF-1.4 ack"), "ack.pdf", "application/pdf")},
        headers=owner,
        content_type="multipart/form-data",
    )
    acknowledgement_id = database.session.get(ComplianceItem, q1.id).acknowledgement_document_id

    response = client.delete(f"{DOCS}/{acknowledgement_id}", headers=owner)

    assert response.status_code == 409
    assert "Undo" in response.get_json()["error"]["message"]
