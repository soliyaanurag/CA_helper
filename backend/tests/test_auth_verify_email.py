"""POST /api/v1/auth/verify-email and /verify-email/resend."""

from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.models import EmailOtp, User
from app.services.auth_service import OTP_MAX_ATTEMPTS
from tests.conftest import emailed_code

VERIFY_URL = "/api/v1/auth/verify-email"
RESEND_URL = "/api/v1/auth/verify-email/resend"
EMAIL = "asha@example.com"
PASSWORD = "Sunrise-2026"


@pytest.fixture()
def signed_up(client, database, mailbox):
    """Sign up; returns the emailed verification code."""
    client.post(
        "/api/v1/auth/signup",
        json={"full_name": "Asha Rao", "email": EMAIL, "password": PASSWORD, "role": "ca"},
    )
    return emailed_code(mailbox[-1])


def verify(client, code, email=EMAIL):
    return client.post(VERIFY_URL, json={"email": email, "code": code})


def error_code(response):
    return response.get_json()["error"]["code"]


def wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


def make_codes_older(database, minutes: int) -> None:
    """Pretend every code was sent `minutes` earlier."""
    database.session.execute(
        update(EmailOtp).values(created_at=EmailOtp.created_at - timedelta(minutes=minutes))
    )
    database.session.commit()


def test_the_emailed_code_verifies_the_email_and_login_works(client, database, signed_up):
    response = verify(client, signed_up, email=" ASHA@example.com ")

    assert response.status_code == 204
    assert database.session.scalar(select(User)).email_verified_at is not None
    login = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200


def test_a_wrong_code_is_refused_and_counted(client, database, signed_up):
    response = verify(client, wrong(signed_up))

    assert response.status_code == 400
    assert error_code(response) == "OTP_INVALID"
    assert database.session.scalar(select(EmailOtp)).attempts == 1
    assert verify(client, signed_up).status_code == 204  # the right code still works


def test_the_code_stops_working_after_too_many_wrong_guesses(client, signed_up):
    for _ in range(OTP_MAX_ATTEMPTS):
        assert error_code(verify(client, wrong(signed_up))) == "OTP_INVALID"

    response = verify(client, signed_up)

    assert response.status_code == 400
    assert error_code(response) == "OTP_EXPIRED"


def test_an_expired_code_is_refused(client, database, signed_up):
    database.session.execute(
        update(EmailOtp).values(expires_at=EmailOtp.expires_at - timedelta(minutes=11))
    )
    database.session.commit()

    response = verify(client, signed_up)

    assert response.status_code == 400
    assert error_code(response) == "OTP_EXPIRED"


def test_an_unknown_email_gets_the_same_error_as_a_wrong_code(client, signed_up):
    response = verify(client, signed_up, email="nobody@example.com")

    assert response.status_code == 400
    assert error_code(response) == "OTP_INVALID"


def test_an_already_verified_email_says_so(client, signed_up):
    verify(client, signed_up)

    response = verify(client, signed_up)

    assert response.status_code == 409
    assert error_code(response) == "EMAIL_ALREADY_VERIFIED"


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", ""])
def test_the_code_must_be_6_digits(client, database, code):
    response = verify(client, code)

    assert response.status_code == 422
    assert "code" in response.get_json()["error"]["details"]["json"]


def test_resend_emails_a_new_code_that_replaces_the_old_one(client, database, signed_up, mailbox):
    make_codes_older(database, minutes=2)

    response = client.post(RESEND_URL, json={"email": EMAIL})

    assert response.status_code == 204
    assert len(mailbox) == 2
    new_code = emailed_code(mailbox[-1])
    if new_code != signed_up:  # 1 in a million they are equal
        assert error_code(verify(client, signed_up)) == "OTP_INVALID"
    assert verify(client, new_code).status_code == 204


def test_resend_sends_at_most_one_code_a_minute(client, signed_up, mailbox):
    response = client.post(RESEND_URL, json={"email": EMAIL})

    assert response.status_code == 204
    assert len(mailbox) == 1  # only the signup email


def test_resend_never_reveals_whether_an_account_exists(client, make_user, mailbox):
    make_user(email="verified@example.com")  # already verified

    unknown = client.post(RESEND_URL, json={"email": "nobody@example.com"})
    verified = client.post(RESEND_URL, json={"email": "verified@example.com"})

    assert unknown.status_code == verified.status_code == 204
    assert mailbox == []


def test_resend_is_rate_limited_to_3_per_minute(client, database):
    statuses = [client.post(RESEND_URL, json={"email": EMAIL}).status_code for _ in range(4)]

    assert statuses == [204, 204, 204, 429]
