"""POST /api/v1/auth/signup: new business and CA accounts start with an unverified email."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import EmailOtp, User
from app.models.base import utcnow
from app.models.email_otp import OtpPurpose
from app.utils.passwords import verify_password
from tests.conftest import emailed_code

SIGNUP_URL = "/api/v1/auth/signup"
PASSWORD = "Sunrise-2026"
NEW_ACCOUNT = {
    "full_name": "Asha Rao",
    "email": "Asha@Example.com",
    "password": PASSWORD,
    "role": "business",
}


def signup(client, **changes):
    return client.post(SIGNUP_URL, json={**NEW_ACCOUNT, **changes})


def test_signup_creates_an_unverified_account(client, database):
    response = signup(client)

    assert response.status_code == 201
    body = response.get_json()
    assert body == {
        "id": body["id"],
        "email": "asha@example.com",  # stored normalized
        "full_name": "Asha Rao",
        "role": "business",
    }
    user = database.session.scalar(select(User))
    assert str(user.id) == body["id"]
    assert user.email_verified_at is None
    assert user.password_hash != PASSWORD
    assert verify_password(user.password_hash, PASSWORD)


def test_signup_emails_a_6_digit_code_stored_only_as_a_hash(client, database, mailbox):
    signup(client)

    [message] = mailbox
    assert message["To"] == "asha@example.com"
    assert message["Subject"] == "Your CA Helper verification code"
    code = emailed_code(message)
    otp = database.session.scalar(select(EmailOtp))
    assert otp.purpose == OtpPurpose.VERIFY_EMAIL
    assert otp.code_hash != code
    assert verify_password(otp.code_hash, code)
    assert otp.expires_at - utcnow() > timedelta(minutes=9)


def test_a_ca_can_sign_up(client, database):
    response = signup(client, role="ca")

    assert response.status_code == 201
    assert response.get_json()["role"] == "ca"


def test_nobody_can_sign_up_as_admin(client, database):
    response = signup(client, role="admin")

    assert response.status_code == 422
    assert "role" in response.get_json()["error"]["details"]["json"]
    assert database.session.scalar(select(User)) is None


def test_an_email_can_have_only_one_account(client, make_user, mailbox):
    make_user(email="asha@example.com")

    response = signup(client, email="ASHA@example.com")

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "EMAIL_TAKEN"
    assert mailbox == []


@pytest.mark.parametrize(
    "password",
    ["Short-1", "no-digits-here", "1234567890", "a1" * 64 + "x"],
    ids=["too short", "no digit", "no letter", "too long"],
)
def test_signup_enforces_the_password_rule(client, database, password):
    response = signup(client, password=password)

    assert response.status_code == 422
    assert response.get_json()["error"]["details"]["json"]["password"] == [
        "Use 8 to 128 characters, with at least one letter and one number."
    ]


def test_signup_needs_a_name_and_a_real_email(client, database):
    response = signup(client, full_name="   ", email="not-an-email")

    assert response.status_code == 422
    assert set(response.get_json()["error"]["details"]["json"]) == {"full_name", "email"}


def test_login_is_refused_until_the_email_is_verified(client, database):
    signup(client)

    response = client.post(
        "/api/v1/auth/login", json={"email": "asha@example.com", "password": PASSWORD}
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_signup_is_rate_limited_to_5_per_minute(client, database):
    statuses = [signup(client, email=f"user{i}@example.com").status_code for i in range(6)]

    assert statuses == [201] * 5 + [429]
