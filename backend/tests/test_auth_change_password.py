"""POST /api/v1/auth/change-password (any logged-in user)."""

import pytest

from app.models.enums import UserRole
from tests.conftest import TEST_PASSWORD

URL = "/api/v1/auth/change-password"
NEW_PASSWORD = "New-Password-7"


def change(client, headers, current=TEST_PASSWORD, new=NEW_PASSWORD):
    return client.post(
        URL, json={"current_password": current, "new_password": new}, headers=headers
    )


def login(client, user, password):
    return client.post("/api/v1/auth/login", json={"email": user.email, "password": password})


@pytest.mark.parametrize("role", list(UserRole))
def test_every_role_can_change_their_password(client, make_user, auth_headers, mailbox, role):
    user = make_user(role=role)

    response = change(client, auth_headers(user))

    assert response.status_code == 204
    assert login(client, user, NEW_PASSWORD).status_code == 200
    assert login(client, user, TEST_PASSWORD).status_code == 401
    [message] = mailbox
    assert message["To"] == user.email
    assert message["Subject"] == "Your CA Helper password was changed"


def test_needs_a_login(client, database):
    response = change(client, headers={})

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "AUTH_REQUIRED"


def test_a_wrong_current_password_is_400_not_401(client, make_user, auth_headers, mailbox):
    # 401 would log the user out in the frontend.
    user = make_user()

    response = change(client, auth_headers(user), current="not-my-password")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "WRONG_PASSWORD"
    assert login(client, user, TEST_PASSWORD).status_code == 200
    assert mailbox == []


def test_the_new_password_must_differ_from_the_current_one(client, make_user, auth_headers):
    user = make_user()

    response = change(client, auth_headers(user), new=TEST_PASSWORD)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "SAME_PASSWORD"


def test_the_new_password_must_follow_the_rule(client, make_user, auth_headers):
    user = make_user()

    response = change(client, auth_headers(user), new="password")

    assert response.status_code == 422
    assert "new_password" in response.get_json()["error"]["details"]["json"]


def test_change_password_is_rate_limited_to_10_per_minute(client, make_user, auth_headers):
    headers = auth_headers(make_user())

    statuses = [change(client, headers, current="wrong").status_code for _ in range(11)]

    assert statuses == [400] * 10 + [429]
