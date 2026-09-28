"""`flask seed-demo` (X1): fictional demo data for every flow, added once."""

from datetime import date

import pytest
from sqlalchemy import func, select

from app import demo_seed
from app.models import (
    Business,
    CaProfile,
    ComplianceItem,
    Document,
    DocumentRequest,
    Engagement,
    Notification,
    ProBonoRequest,
    Rating,
    User,
)
from app.models.marketplace import CaVerificationStatus
from app.services import compliance_service
from tests.test_seed_command import DEMO_ENV

TODAY = date(2026, 9, 28)


@pytest.fixture(autouse=True)
def _env_and_today(monkeypatch):
    for name, value in DEMO_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(compliance_service, "today_in_india", lambda: TODAY)
    monkeypatch.setattr(demo_seed, "today_in_india", lambda: TODAY)


def run(app):
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    return result.output


def count(database, model, *where):
    return database.session.scalar(select(func.count()).select_from(model).where(*where))


def test_demo_data_covers_every_flow(app, database, client):
    output = run(app)

    assert "Demo data added: 14 businesses (the richest one: business@demo.local)" in output
    assert count(database, Business) == 14
    demo = database.session.scalar(
        select(Business)
        .join(User, Business.user_id == User.id)
        .where(User.email == "business@demo.local")
    )
    assert demo.legal_name == "Asha Traders"
    statuses = set(database.session.scalars(select(Engagement.status)))
    assert statuses == {
        "requested",
        "quoted",
        "active",
        "completed",
        "declined",
        "expired",
        "cancelled",
    }
    every_status = {"upcoming", "docs_pending", "ready", "with_ca", "filed", "filed_verified"}
    filing_statuses = set(database.session.scalars(select(ComplianceItem.status)))
    assert every_status | {"overdue"} <= filing_statuses
    assert count(database, Rating) > 0
    assert count(database, DocumentRequest) == 3
    assert count(database, Document) >= 10
    assert count(database, Notification) >= 3
    assert count(database, ProBonoRequest) == 1
    pending = database.session.scalars(
        select(CaProfile).where(CaProfile.verification_status == CaVerificationStatus.PENDING)
    ).all()
    assert len(pending) == 1 and pending[0].cop_document_id is not None


def test_the_demo_business_sees_its_segment_and_files(app, database, client):
    run(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "business@demo.local", "password": DEMO_ENV["DEMO_BUSINESS_PASSWORD"]},
    )
    headers = {"Authorization": "Bearer " + login.get_json()["access_token"]}
    filings = client.get("/api/v1/compliance/items?form_code=gstr_3b", headers=headers).get_json()

    insights = client.get(
        f"/api/v1/compliance/items/{filings[0]['id']}/peer-insights", headers=headers
    ).get_json()
    assert insights["scope"] == "segment"
    assert insights["business_count"] == 10
    vault = client.get("/api/v1/documents", headers=headers).get_json()
    assert vault["total"] >= 7
    document = vault["items"][0]
    opened = client.get(f"/api/v1/documents/{document['id']}/file", headers=headers)
    assert opened.data.startswith(b"%PDF-")
    requests = client.get("/api/v1/ca-workspace/document-requests", headers=headers).get_json()
    assert len(requests) == 1  # one open; the other was fulfilled


def test_the_demo_ca_sees_clients_and_batches(app, database, client):
    run(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ca@demo.local", "password": DEMO_ENV["DEMO_CA_PASSWORD"]},
    )
    headers = {"Authorization": "Bearer " + login.get_json()["access_token"]}

    clients = client.get("/api/v1/ca-workspace/clients", headers=headers).get_json()
    batches = client.get("/api/v1/ca-workspace/batches", headers=headers).get_json()

    assert len(clients) == 3
    assert clients[0]["score"] > 0
    assert max(len(batch["filings"]) for batch in batches) == 3  # same form, same day

    # The demo script's CA steps work: take the pro-bono request, file for Asha Traders.
    queue = client.get("/api/v1/marketplace/pro-bono-queue", headers=headers).get_json()
    taken = client.post(
        f"/api/v1/marketplace/pro-bono/{queue['requests'][0]['id']}/accept", headers=headers
    )
    assert taken.status_code == 200, taken.get_json()
    asha = next(row for row in clients if row["business_name"] == "Asha Traders")
    workspace = client.get(
        f"/api/v1/ca-workspace/clients/{asha['business_id']}", headers=headers
    ).get_json()
    filing_id = workspace["filings"][0]["filing"]["id"]
    filed = client.post(
        f"/api/v1/ca-workspace/clients/{asha['business_id']}/filings/{filing_id}/mark-filed",
        data={"acknowledgement_no": "AA271026000001"},
        headers=headers,
        content_type="multipart/form-data",
    )
    assert filed.get_json()["status"] == "filed"


def test_the_demo_admin_verifies_the_pending_ca(app, database, client):
    run(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@demo.local", "password": DEMO_ENV["DEMO_ADMIN_PASSWORD"]},
    )
    headers = {"Authorization": "Bearer " + login.get_json()["access_token"]}
    [pending] = client.get("/api/v1/admin/cas?status=pending", headers=headers).get_json()

    certificate = client.get(f"/api/v1/admin/cas/{pending['id']}/certificate", headers=headers)
    verified = client.post(f"/api/v1/admin/cas/{pending['id']}/verify", headers=headers)

    assert certificate.data.startswith(b"%PDF-")
    assert verified.get_json()["verification_status"] == "verified"


def test_seed_demo_runs_once(app, database):
    run(app)
    second = run(app)

    assert "already there" in second
    assert count(database, Business) == 14
