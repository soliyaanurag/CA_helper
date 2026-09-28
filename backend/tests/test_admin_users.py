"""Admin: suspend and reactivate accounts (AD4), the audit log (AD8) and the filing numbers
on the admin dashboard (AD5)."""

from datetime import UTC, date, datetime

import pytest

from app.models import AdminAuditLog, ComplianceItem, Engagement, Notification, User
from app.models.compliance import ComplianceStatus
from app.models.enums import UserRole
from app.models.marketplace import EngagementStatus
from app.services import compliance_service
from app.utils.passwords import hash_password
from tests.conftest import TEST_PASSWORD
from tests.test_ca_workspace_clients import engage, filing, make_ca

BASE = "/api/v1/admin"


@pytest.fixture()
def admin(make_user, auth_headers):
    user = make_user(role=UserRole.ADMIN, full_name="Admin One")
    return user, auth_headers(user)


def suspend(client, headers, user_id, reason="Fake documents"):
    return client.post(f"{BASE}/users/{user_id}/suspend", json={"reason": reason}, headers=headers)


def login(client, user):
    return client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})


# --- Suspend and reactivate (AD4) --------------------------------------------------------


def test_a_suspended_user_cannot_log_in_or_use_a_token(client, admin, make_user, auth_headers):
    _, headers = admin
    user = make_user(role=UserRole.BUSINESS, password_hash=hash_password(TEST_PASSWORD))
    old_token = auth_headers(user)

    response = suspend(client, headers, user.id)

    assert response.status_code == 200
    assert response.get_json()["is_active"] is False
    refused = login(client, user)
    assert refused.status_code == 403
    assert refused.get_json()["error"]["code"] == "ACCOUNT_INACTIVE"
    assert "suspended" in refused.get_json()["error"]["message"]
    assert client.get("/api/v1/auth/me", headers=old_token).status_code == 401


def test_reactivate_lets_them_log_in_again(client, admin, make_user):
    _, headers = admin
    user = make_user(role=UserRole.BUSINESS)
    suspend(client, headers, user.id)

    response = client.post(f"{BASE}/users/{user.id}/reactivate", headers=headers)

    assert response.get_json()["is_active"] is True
    assert login(client, user).status_code == 200
    again = client.post(f"{BASE}/users/{user.id}/reactivate", headers=headers)
    assert again.get_json()["error"]["code"] == "NOT_SUSPENDED"


def test_suspend_checks(client, admin):
    admin_user, headers = admin

    myself = suspend(client, headers, admin_user.id)
    unknown = suspend(client, headers, "00000000-0000-0000-0000-000000000000")

    assert myself.status_code == 409
    assert myself.get_json()["error"]["code"] == "CANNOT_SUSPEND_SELF"
    assert unknown.get_json()["error"]["code"] == "USER_NOT_FOUND"


def test_suspending_twice_is_refused(client, admin, make_user):
    _, headers = admin
    user = make_user(role=UserRole.BUSINESS)
    suspend(client, headers, user.id)

    assert suspend(client, headers, user.id).get_json()["error"]["code"] == "ALREADY_SUSPENDED"


def test_a_suspended_ca_leaves_the_marketplace_and_open_requests_are_cancelled(
    client, admin, business_with_filings, database, make_user, auth_headers, mailbox
):
    _, headers = admin
    ca_user, profile = make_ca(make_user, database)
    requested = engage(
        database, business_with_filings, profile, [filing(database)], EngagementStatus.REQUESTED
    )
    active = engage(
        database,
        business_with_filings,
        profile,
        [filing(database, "gstr_3b")],
        EngagementStatus.ACTIVE,
    )
    owner = database.session.get(User, business_with_filings.user_id)
    owner_headers = auth_headers(owner)
    listed = client.get("/api/v1/marketplace/cas", headers=owner_headers).get_json()
    assert str(profile.id) in [row["id"] for row in listed["items"]]
    mailbox.clear()

    suspend(client, headers, ca_user.id)

    database.session.expire_all()
    assert database.session.get(Engagement, requested.id).status == "cancelled"
    assert database.session.get(Engagement, active.id).status == "active"  # kept
    listed = client.get("/api/v1/marketplace/cas", headers=owner_headers).get_json()
    assert str(profile.id) not in [row["id"] for row in listed["items"]]
    note = database.session.query(Notification).filter_by(user_id=owner.id).one()
    assert note.title == "Your CA request was cancelled"
    assert [message["To"] for message in mailbox] == [owner.email]
    entry = database.session.query(AdminAuditLog).one()
    assert entry.details == {"reason": "Fake documents", "cancelled_requests": 1}


@pytest.mark.parametrize("role", [UserRole.BUSINESS, UserRole.CA])
def test_only_admins_suspend(client, make_user, auth_headers, role):
    target = make_user(role=UserRole.BUSINESS)
    response = suspend(client, auth_headers(make_user(role=role)), target.id)

    assert response.status_code == 403


# --- Audit log (AD8) ---------------------------------------------------------------------


def test_audit_log_lists_actions_newest_first(client, admin, make_user):
    _, headers = admin
    user = make_user(role=UserRole.BUSINESS, full_name="Asha Rao")
    suspend(client, headers, user.id, reason=" ")
    client.post(f"{BASE}/users/{user.id}/reactivate", headers=headers)

    response = client.get(f"{BASE}/audit-log?page_size=1", headers=headers)

    body = response.get_json()
    assert response.status_code == 200
    assert body["total"] == 2
    [entry] = body["items"]
    assert entry["action"] == "user.reactivate"
    assert (entry["admin_name"], entry["target_type"], entry["target_name"]) == (
        "Admin One",
        "user",
        "Asha Rao",
    )
    second = client.get(f"{BASE}/audit-log?page=2&page_size=1", headers=headers).get_json()
    assert second["items"][0]["action"] == "user.suspend"
    assert second["items"][0]["details"]["reason"] is None  # a blank reason is not kept


def test_audit_log_is_for_admins(client, make_user, auth_headers):
    response = client.get(f"{BASE}/audit-log", headers=auth_headers(make_user(role=UserRole.CA)))

    assert response.status_code == 403


# --- Filing numbers (AD5) ----------------------------------------------------------------


def test_stats_count_filings_by_status_and_the_overdue_rate(
    client, admin, business_with_filings, database, monkeypatch
):
    _, headers = admin
    monkeypatch.setattr(compliance_service, "today_in_india", lambda: date(2026, 9, 28))
    # Q1 GSTR-1 was due in July: filed on time. Q1 GSTR-3B: filed late. The rest: overdue.
    on_time = filing(database, "gstr_1", "Q1 2026-27")
    on_time.status = ComplianceStatus.FILED
    on_time.filed_at = datetime(2026, 7, 1, 5, 0, tzinfo=UTC)
    late = filing(database, "gstr_3b", "Q1 2026-27")
    late.status = ComplianceStatus.FILED
    late.filed_at = datetime(2026, 9, 1, 5, 0, tzinfo=UTC)
    database.session.commit()
    all_filings = database.session.query(ComplianceItem).all()
    due = [item for item in all_filings if item.due_date < date(2026, 9, 28)]

    stats = client.get(f"{BASE}/stats", headers=headers).get_json()

    assert stats["filings_by_status"]["filed"] == 2
    assert sum(stats["filings_by_status"].values()) == len(all_filings)
    assert stats["filings_due_so_far"] == len(due)
    assert stats["filings_late"] == len(due) - 1
    assert stats["overdue_rate"] == round((len(due) - 1) * 100 / len(due), 1)


def test_overdue_rate_is_empty_before_anything_is_due(client, admin):
    stats = client.get(f"{BASE}/stats", headers=admin[1]).get_json()

    assert stats["overdue_rate"] is None
    assert stats["filings_due_so_far"] == 0
