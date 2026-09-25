"""GET /api/v1/auth/me, JWT error responses, and the roles_required decorator."""

from datetime import timedelta

from flask_jwt_extended import create_access_token

from app.core.db.enums import UserRole

ME_URL = "/api/v1/auth/me"


def test_me_returns_the_logged_in_user(client, make_user, auth_headers):
    user = make_user(role=UserRole.ADMIN, email="admin@example.com", full_name="Ravi Admin")

    response = client.get(ME_URL, headers=auth_headers(user))

    assert response.status_code == 200
    assert response.get_json() == {
        "id": str(user.id),
        "email": "admin@example.com",
        "full_name": "Ravi Admin",
        "role": "admin",
    }


def test_me_without_token_is_401(client, database):
    response = client.get(ME_URL)

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "AUTH_REQUIRED"


def test_me_with_bad_token_is_401(client, database):
    response = client.get(ME_URL, headers={"Authorization": "Bearer not.a.jwt"})

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "TOKEN_INVALID"


def test_me_with_expired_token_is_401(client, make_user):
    user = make_user()
    token = create_access_token(
        identity=str(user.id), additional_claims={"role": "business"}, expires_delta=timedelta(-1)
    )

    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "TOKEN_EXPIRED"


def test_token_of_deactivated_user_is_401(client, make_user, auth_headers, database):
    user = make_user()
    headers = auth_headers(user)
    user.is_active = False
    database.session.commit()

    response = client.get(ME_URL, headers=headers)

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "ACCOUNT_INACTIVE"


def test_token_for_unknown_user_id_is_401(client, database):
    token = create_access_token(identity="not-a-uuid", additional_claims={"role": "admin"})

    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_role_is_checked_against_the_database_not_the_token(
    client, make_user, auth_headers, database
):
    # A token issued while the user was an admin stops opening admin pages once
    # the stored role changes.
    user = make_user(role=UserRole.ADMIN)
    headers = auth_headers(user)
    user.role = UserRole.BUSINESS
    database.session.commit()

    response = client.get("/api/v1/admin/dashboard", headers=headers)

    assert response.status_code == 403


def test_openapi_marks_login_and_health_public_and_the_rest_protected(client):
    spec = client.get("/api/openapi.json").get_json()

    assert spec["security"] == [{"bearerAuth": []}]
    assert spec["paths"]["/api/v1/auth/login"]["post"]["security"] == []
    assert spec["paths"]["/api/health"]["get"]["security"] == []
    assert "security" not in spec["paths"]["/api/v1/auth/me"]["get"]
