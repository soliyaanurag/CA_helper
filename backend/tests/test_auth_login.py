"""POST /api/v1/auth/login and the authenticate() service."""

from datetime import UTC, datetime

from argon2 import PasswordHasher
from flask_jwt_extended import decode_token

from app.models.enums import UserRole
from app.services import auth_service
from tests.conftest import TEST_PASSWORD

LOGIN_URL = "/api/v1/auth/login"


def login(client, email: str, password: str = TEST_PASSWORD):
    return client.post(LOGIN_URL, json={"email": email, "password": password})


def test_login_success_returns_token_and_user(client, make_user):
    user = make_user(role=UserRole.CA, email="ca@example.com", full_name="Asha Rao")

    response = login(client, "ca@example.com")

    assert response.status_code == 200
    body = response.get_json()
    assert body["user"] == {
        "id": str(user.id),
        "email": "ca@example.com",
        "full_name": "Asha Rao",
        "role": "ca",
    }
    claims = decode_token(body["access_token"])
    assert claims["sub"] == str(user.id)
    assert claims["role"] == "ca"
    assert claims["exp"] > claims["iat"]


def test_login_email_is_trimmed_and_case_insensitive(client, make_user):
    make_user(email="owner@example.com")

    response = login(client, "  Owner@Example.COM ")

    assert response.status_code == 200


def test_wrong_password_and_unknown_email_get_the_same_error(client, make_user):
    make_user(email="owner@example.com")

    wrong_password = login(client, "owner@example.com", "not-the-password")
    unknown_email = login(client, "nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    wrong_password_error = wrong_password.get_json()["error"]
    unknown_email_error = unknown_email.get_json()["error"]
    assert wrong_password_error["code"] == unknown_email_error["code"] == "INVALID_CREDENTIALS"
    assert wrong_password_error["message"] == unknown_email_error["message"]


def test_unknown_email_still_checks_a_password_hash(client, database, monkeypatch):
    # Guards the timing protection: an unknown email must cost one argon2 verify too.
    checked = []
    real_verify = auth_service.verify_password
    monkeypatch.setattr(
        auth_service, "verify_password", lambda h, p: checked.append(h) or real_verify(h, p)
    )

    login(client, "nobody@example.com")

    assert checked == [auth_service._dummy_hash()]


def test_inactive_user_is_rejected(client, make_user):
    make_user(email="gone@example.com", is_active=False)

    response = login(client, "gone@example.com")

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ACCOUNT_INACTIVE"


def test_soft_deleted_user_is_rejected(client, make_user):
    make_user(email="deleted@example.com", deleted_at=datetime.now(UTC))

    response = login(client, "deleted@example.com")

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ACCOUNT_INACTIVE"


def test_unverified_email_is_rejected(client, make_user):
    make_user(email="new@example.com", email_verified_at=None)

    response = login(client, "new@example.com")

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_unverified_user_with_wrong_password_gets_invalid_credentials(client, make_user):
    make_user(email="new@example.com", email_verified_at=None)

    response = login(client, "new@example.com", "not-the-password")

    assert response.status_code == 401


def test_inactive_user_with_wrong_password_gets_invalid_credentials(client, make_user):
    # The account state is revealed only to someone who knows the password.
    make_user(email="gone@example.com", is_active=False)

    response = login(client, "gone@example.com", "not-the-password")

    assert response.status_code == 401


def test_outdated_hash_is_rehashed_on_login(client, make_user):
    weak_hash = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(TEST_PASSWORD)
    user = make_user(email="old@example.com", password_hash=weak_hash)

    assert login(client, "old@example.com").status_code == 200

    assert user.password_hash != weak_hash
    assert not auth_service.needs_rehash(user.password_hash)
    assert login(client, "old@example.com").status_code == 200


def test_invalid_body_is_a_validation_error(client, database):
    response = client.post(LOGIN_URL, json={"email": ""})

    assert response.status_code == 422
    assert set(response.get_json()["error"]["details"]["json"]) == {"email", "password"}


def test_login_is_rate_limited_to_10_per_minute(client, database):
    statuses = [login(client, "nobody@example.com").status_code for _ in range(11)]

    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    response = login(client, "nobody@example.com")
    assert response.get_json()["error"]["code"] == "TOO_MANY_REQUESTS"
