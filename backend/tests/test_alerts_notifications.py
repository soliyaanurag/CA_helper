"""The notification tray and the email switch (AL1, AL3).

notify() adds a tray entry; email_notice() emails its text after the commit (unless the
user switched notification emails off). The tray endpoints work for every role, on own rows only.
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
SETTINGS = "/api/v1/auth/settings"


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


def test_email_notice_emails_the_tray_text(make_user, mailbox, database):
    user = make_user(full_name="Asha Rao")

    alerts_service.notify(user, NotificationType.OVERDUE, "GSTR-1 is late", "Due 13 Oct")
    db.session.commit()
    alerts_service.email_notice(user, "GSTR-1 is late", "Due 13 Oct")

    assert len(mailbox) == 1
    assert mailbox[0]["To"] == user.email
    assert mailbox[0]["Subject"] == "GSTR-1 is late"
    assert "Hello Asha Rao" in mailbox[0].get_content()


def test_notify_respects_the_email_switch_but_always_adds_to_the_tray(
    client, make_user, auth_headers, mailbox, database
):
    user = make_user()
    body = {"email_notifications": False}
    client.put(SETTINGS, json=body, headers=auth_headers(user))

    alerts_service.notify(user, NotificationType.DEADLINE_REMINDER, "Soon", "Body")
    alerts_service.notify(user, NotificationType.OVERDUE, "Late", "Body")
    db.session.commit()
    database.session.refresh(user)
    alerts_service.email_notice(user, "Soon", "Body")
    alerts_service.email_notice(user, "Late", "Body")

    assert database.session.query(Notification).count() == 2
    assert mailbox == []


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


def test_the_tray_shows_only_own_entries(client, make_user, auth_headers, database):
    me, other = make_user(), make_user()
    add_notifications(me, 2)
    add_notifications(other, 1)
    dismissed = database.session.query(Notification).filter_by(user_id=me.id).first()
    database.session.delete(dismissed)
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
    ],
)
def test_the_tray_needs_a_login(client, database, method, url):
    assert getattr(client, method)(f"{BASE}{url}").status_code == 401


# --- The email switch (AL3) ---------------------------------------------------------------


@pytest.mark.parametrize("role", [UserRole.BUSINESS, UserRole.CA])
def test_emails_are_on_by_default(client, make_user, auth_headers, role):
    response = client.get(SETTINGS, headers=auth_headers(make_user(role=role)))

    assert response.status_code == 200
    assert response.get_json() == {"email_notifications": True}


def test_switching_emails_off_and_on(client, make_user, auth_headers):
    headers = auth_headers(make_user())

    off = client.put(SETTINGS, json={"email_notifications": False}, headers=headers)

    assert off.get_json() == {"email_notifications": False}
    assert client.get(SETTINGS, headers=headers).get_json() == {"email_notifications": False}
    on = client.put(SETTINGS, json={"email_notifications": True}, headers=headers)
    assert on.get_json() == {"email_notifications": True}


def test_code_emails_are_sent_even_when_emails_are_off(client, make_user, auth_headers, mailbox):
    user = make_user(email="asha@example.com")
    client.put(SETTINGS, json={"email_notifications": False}, headers=auth_headers(user))

    client.post("/api/v1/auth/forgot-password", json={"email": "asha@example.com"})

    assert [message["To"] for message in mailbox] == ["asha@example.com"]


def test_settings_need_a_login(client, database):
    assert client.get(SETTINGS).status_code == 401


def test_admins_have_no_settings_page(client, make_user, auth_headers):
    headers = auth_headers(make_user(role=UserRole.ADMIN))
    assert client.get(SETTINGS, headers=headers).status_code == 403
