"""GET /api/v1/auth/me, JWT error responses, and the roles_required decorator."""

import re
import uuid
from datetime import timedelta

from flask_jwt_extended import create_access_token

from app.models import UserRole

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


def test_token_of_a_user_that_no_longer_exists_is_401(client, make_user, auth_headers, database):
    user = make_user()
    headers = auth_headers(user)
    database.session.delete(user)
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


PUBLIC = {
    "/api/health",
    "/api/v1/auth/signup",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/verify-email/resend",
    "/api/v1/auth/login",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
}


def test_every_other_api_route_needs_a_login(app, client):
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/") or rule.rule in PUBLIC:
            continue
        url = re.sub(r"<[^>]+>", str(uuid.uuid4()), rule.rule)
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            response = client.open(url, method=method)
            assert response.status_code == 401, f"{method} {rule.rule} is not protected"
