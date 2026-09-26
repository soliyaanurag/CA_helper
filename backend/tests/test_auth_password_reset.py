"""POST /api/v1/auth/forgot-password and /reset-password."""

from datetime import timedelta

import pytest
from sqlalchemy import update

from app.models import EmailOtp
from tests.conftest import TEST_PASSWORD, emailed_code

FORGOT_URL = "/api/v1/auth/forgot-password"
RESET_URL = "/api/v1/auth/reset-password"
EMAIL = "owner@example.com"
NEW_PASSWORD = "New-Password-7"


def forgot(client, email=EMAIL):
    return client.post(FORGOT_URL, json={"email": email})


def reset(client, code, new_password=NEW_PASSWORD, email=EMAIL):
    return client.post(RESET_URL, json={"email": email, "code": code, "new_password": new_password})


def login(client, password, email=EMAIL):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.fixture()
def owner(make_user):
    return make_user(email=EMAIL, full_name="Ravi Kumar")


def test_forgot_password_emails_a_code_that_resets_the_password(client, owner, mailbox):
    assert forgot(client, email=" Owner@Example.com ").status_code == 204
    [message] = mailbox
    assert message["To"] == EMAIL
    assert message["Subject"] == "Your CA Helper password reset code"

    response = reset(client, emailed_code(message))

    assert response.status_code == 204
    assert login(client, NEW_PASSWORD).status_code == 200
    assert login(client, TEST_PASSWORD).status_code == 401
    assert mailbox[-1]["Subject"] == "Your CA Helper password was changed"


def test_forgot_password_never_reveals_whether_an_account_exists(client, make_user, mailbox):
    make_user(email="gone@example.com", is_active=False)

    unknown = forgot(client, email="nobody@example.com")
    inactive = forgot(client, email="gone@example.com")

    assert unknown.status_code == inactive.status_code == 204
    assert mailbox == []


def test_forgot_password_sends_at_most_one_code_a_minute(client, database, owner, mailbox):
    forgot(client)
    forgot(client)
    assert len(mailbox) == 1

    database.session.execute(
        update(EmailOtp).values(created_at=EmailOtp.created_at - timedelta(minutes=2))
    )
    database.session.commit()
    forgot(client)

    assert len(mailbox) == 2


def test_a_wrong_code_does_not_change_the_password(client, owner, mailbox):
    forgot(client)
    code = emailed_code(mailbox[0])

    response = reset(client, f"{(int(code) + 1) % 1_000_000:06d}")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "OTP_INVALID"
    assert login(client, TEST_PASSWORD).status_code == 200


def test_a_reset_code_works_only_once(client, owner, mailbox):
    forgot(client)
    code = emailed_code(mailbox[0])
    reset(client, code)

    response = reset(client, code, new_password="Another-Password-8")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "OTP_INVALID"


def test_the_new_password_must_follow_the_rule(client, owner, mailbox):
    forgot(client)

    response = reset(client, emailed_code(mailbox[0]), new_password="short")

    assert response.status_code == 422
    assert "new_password" in response.get_json()["error"]["details"]["json"]


def test_a_verification_code_cannot_reset_a_password(client, database, mailbox):
    client.post(
        "/api/v1/auth/signup",
        json={"full_name": "Asha", "email": EMAIL, "password": "Sunrise-2026", "role": "business"},
    )

    response = reset(client, emailed_code(mailbox[0]))

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "OTP_INVALID"


def test_resetting_the_password_also_verifies_the_email(client, make_user, mailbox):
    make_user(email=EMAIL, email_verified_at=None)
    forgot(client)

    reset(client, emailed_code(mailbox[0]))

    assert login(client, NEW_PASSWORD).status_code == 200


def test_forgot_password_is_rate_limited_to_3_per_minute(client, database):
    statuses = [forgot(client).status_code for _ in range(4)]

    assert statuses == [204, 204, 204, 429]
