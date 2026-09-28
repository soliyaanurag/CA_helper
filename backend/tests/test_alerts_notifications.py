"""The notification tray and email settings (AL1, AL3).

notify() adds a tray entry and, with email=True, emails it after the commit (unless the
user switched that type off). The tray endpoints work for every role, on own rows only.
"""

from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Notification
from app.models.alerts import NotificationType
from app.models.base import utcnow
from app.models.enums import UserRole
from app.services import alerts_service

BASE = "/api/v1/alerts"


def add_notifications(user, count, notification_type=NotificationType.ENGAGEMENT_UPDATE):
    """Add `count` tray entries, each a minute newer than the one before."""
    start = utcnow() - timedelta(hours=1)
    for number in range(count):
        note = alerts_service.notify(user, notification_type, f"Title {number}", "Body")
        note.created_at = start + timedelta(minutes=number)
    db.session.commit()


# --- notify() ----------------------------------------------------------------------------


def test_notify_adds_a_tray_entry_without_email_by_default(make_user, mailbox, database):
    user = make_user()

    alerts_service.notify(user, NotificationType.OVERDUE, "Late", "Body", "/business")
    db.session.commit()

    note = database.session.query(Notification).one()
    assert (note.user_id, note.type, note.link, note.read_at) == (
        user.id,
        "overdue",
        "/business",
        None,
    )
    assert mailbox == []


def test_notify_emails_only_after_the_commit(make_user, mailbox, database):
    user = make_user(full_name="Asha Rao")

    alerts_service.notify(
        user, NotificationType.OVERDUE, "GSTR-1 is late", "Due 13 Oct", email=True
    )
    assert mailbox == []  # nothing is sent before the commit
    db.session.commit()

    assert len(mailbox) == 1
    assert mailbox[0]["To"] == user.email
    assert mailbox[0]["Subject"] == "GSTR-1 is late"
    assert "Hello Asha Rao" in mailbox[0].get_content()


def test_a_rolled_back_notification_sends_no_email(make_user, mailbox, database):
    user = make_user()

    alerts_service.notify(user, NotificationType.OVERDUE, "Late", "Body", email=True)
    db.session.rollback()
    db.session.commit()  # a later commit must not send the dropped email

    assert mailbox == []
    assert database.session.query(Notification).count() == 0


def test_notify_respects_the_email_setting_but_always_adds_to_the_tray(
    client, make_user, auth_headers, mailbox, database
):
    user = make_user()
    body = {"items": [{"type": "deadline_reminder", "email_enabled": False}]}
    client.put(f"{BASE}/settings", json=body, headers=auth_headers(user))

    alerts_service.notify(user, NotificationType.DEADLINE_REMINDER, "Soon", "Body", email=True)
    alerts_service.notify(user, NotificationType.OVERDUE, "Late", "Body", email=True)
    db.session.commit()

    assert database.session.query(Notification).count() == 2
    assert [message["Subject"] for message in mailbox] == ["Late"]


# --- The tray endpoints ------------------------------------------------------------------


@pytest.mark.parametrize("role", list(UserRole))
def test_every_role_sees_its_tray_newest_first(client, make_user, auth_headers, role):
    user = make_user(role=role)
    add_notifications(user, 3)

    response = client.get(f"{BASE}/notifications?page_size=2", headers=auth_headers(user))

    data = response.get_json()
    assert response.status_code == 200
    assert (data["page"], data["page_size"], data["total"]) == (1, 2, 3)
    assert [item["title"] for item in data["items"]] == ["Title 2", "Title 1"]
    assert data["items"][0]["read_at"] is None


def test_the_tray_shows_only_own_live_entries(client, make_user, auth_headers, database):
    me, other = make_user(), make_user()
    add_notifications(me, 2)
    add_notifications(other, 1)
    dismissed = database.session.query(Notification).filter_by(user_id=me.id).first()
    dismissed.deleted_at = utcnow()
    dismissed.is_active = False
    database.session.commit()

    data = client.get(f"{BASE}/notifications", headers=auth_headers(me)).get_json()

    assert data["total"] == 1
    count = client.get(f"{BASE}/notifications/unread-count", headers=auth_headers(me))
    assert count.get_json() == {"unread": 1}


def test_mark_one_read_then_all(client, make_user, auth_headers, database):
    user = make_user()
    add_notifications(user, 3)
    headers = auth_headers(user)
    first = client.get(f"{BASE}/notifications", headers=headers).get_json()["items"][0]

    response = client.post(f"{BASE}/notifications/{first['id']}/read", headers=headers)

    assert response.status_code == 200
    assert response.get_json()["read_at"] is not None
    assert client.get(f"{BASE}/notifications/unread-count", headers=headers).get_json() == {
        "unread": 2
    }
    assert client.post(f"{BASE}/notifications/read-all", headers=headers).get_json() == {
        "unread": 0
    }
    assert client.get(f"{BASE}/notifications/unread-count", headers=headers).get_json() == {
        "unread": 0
    }


def test_nobody_can_mark_another_users_entry(client, make_user, auth_headers, database):
    owner, other = make_user(), make_user()
    add_notifications(owner, 1)
    note = database.session.query(Notification).one()

    response = client.post(f"{BASE}/notifications/{note.id}/read", headers=auth_headers(other))

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"
    client.post(f"{BASE}/notifications/read-all", headers=auth_headers(other))
    database.session.expire_all()
    assert database.session.get(Notification, note.id).read_at is None


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", "/notifications"),
        ("get", "/notifications/unread-count"),
        ("post", "/notifications/read-all"),
        ("get", "/settings"),
    ],
)
def test_tray_and_settings_need_a_login(client, database, method, url):
    assert getattr(client, method)(f"{BASE}{url}").status_code == 401


# --- Settings (AL3) ----------------------------------------------------------------------


@pytest.mark.parametrize("role", [UserRole.BUSINESS, UserRole.CA])
def test_settings_default_to_on_with_engagement_emails_always_sent(
    client, make_user, auth_headers, role
):
    response = client.get(f"{BASE}/settings", headers=auth_headers(make_user(role=role)))

    assert response.status_code == 200
    assert response.get_json() == {
        "items": [
            {"type": "deadline_reminder", "email_enabled": True},
            {"type": "overdue", "email_enabled": True},
            {"type": "document_request", "email_enabled": True},
            {"type": "regulatory_update", "email_enabled": True},
        ],
        "always_emailed": ["engagement_update", "account"],
    }


def test_saving_settings_twice_keeps_one_row_per_type(client, make_user, auth_headers, database):
    headers = auth_headers(make_user())
    off = {"items": [{"type": "overdue", "email_enabled": False}]}
    client.put(f"{BASE}/settings", json=off, headers=headers)
    on_again = {"items": [{"type": "overdue", "email_enabled": True}]}

    response = client.put(f"{BASE}/settings", json=on_again, headers=headers)

    assert response.status_code == 200
    overdue = [item for item in response.get_json()["items"] if item["type"] == "overdue"]
    assert overdue == [{"type": "overdue", "email_enabled": True}]
    off_again = client.put(f"{BASE}/settings", json=off, headers=headers).get_json()
    assert {"type": "overdue", "email_enabled": False} in off_again["items"]
    assert {"type": "deadline_reminder", "email_enabled": True} in off_again["items"]


def test_engagement_emails_cannot_be_switched_off(client, make_user, auth_headers):
    body = {"items": [{"type": "engagement_update", "email_enabled": False}]}

    response = client.put(f"{BASE}/settings", json=body, headers=auth_headers(make_user()))

    assert response.status_code == 422


def test_admins_have_no_settings_page(client, make_user, auth_headers):
    headers = auth_headers(make_user(role=UserRole.ADMIN))
    assert client.get(f"{BASE}/settings", headers=headers).status_code == 403
