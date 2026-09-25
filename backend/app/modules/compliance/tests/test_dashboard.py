"""GET /api/v1/compliance/dashboard: the business owner's dashboard, for role business only."""

import pytest

from app.core.db.enums import UserRole

URL = "/api/v1/compliance/dashboard"


def test_welcomes_the_user(client, make_user, auth_headers):
    user = make_user(role=UserRole.BUSINESS, full_name="Meera Shah")

    response = client.get(URL, headers=auth_headers(user))

    assert response.status_code == 200
    assert response.get_json() == {"message": "Welcome, Meera Shah"}


@pytest.mark.parametrize("role", [UserRole.CA, UserRole.ADMIN])
def test_other_roles_are_forbidden(client, make_user, auth_headers, role):
    response = client.get(URL, headers=auth_headers(make_user(role=role)))

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "FORBIDDEN"


def test_requires_login(client, database):
    response = client.get(URL)

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "AUTH_REQUIRED"
