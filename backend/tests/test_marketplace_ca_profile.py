"""GET/PUT /api/v1/marketplace/ca-profile: a CA's own practice profile."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import CaProfile
from app.models.enums import UserRole
from app.models.marketplace import CaVerificationStatus

URL = "/api/v1/marketplace/ca-profile"

PROFILE = {
    "membership_no": "123456",
    "cop_number": "COP-7788",
    "city": "Pune",
    "languages": ["marathi", "english"],
    "specializations": ["gstr_3b", "itr"],
    "capacity": 20,
    "years_experience": 5,
    "about": "GST and ITR for small traders.",
}


@pytest.fixture()
def ca(make_user):
    return make_user(role=UserRole.CA, full_name="Meera Shah")


def put_profile(client, headers, **changes):
    return client.put(URL, json={**PROFILE, **changes}, headers=headers)


def set_status(database, user, status):
    profile = database.session.query(CaProfile).filter_by(user_id=user.id).one()
    profile.verification_status = status
    database.session.commit()


def test_no_profile_yet_is_404(client, ca, auth_headers):
    response = client.get(URL, headers=auth_headers(ca))

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "CA_PROFILE_NOT_FOUND"


def test_saving_creates_a_pending_profile(client, ca, auth_headers):
    response = put_profile(client, auth_headers(ca), city="  Pune  ")

    assert response.status_code == 200
    body = response.get_json()
    assert body["verification_status"] == "pending"
    assert body["city"] == "Pune"  # trimmed
    # Codes are stored once each, in the fixed list order.
    assert body["languages"] == ["english", "marathi"]
    assert body["specializations"] == ["itr", "gstr_3b"]
    assert client.get(URL, headers=auth_headers(ca)).get_json() == body


def test_saving_again_updates_the_same_profile(client, ca, auth_headers, database):
    put_profile(client, auth_headers(ca))

    response = put_profile(client, auth_headers(ca), capacity=35, about="")

    assert response.get_json()["capacity"] == 35
    assert response.get_json()["about"] == ""
    assert database.session.query(CaProfile).count() == 1


def test_verified_profile_stays_verified_after_a_small_edit(client, ca, auth_headers, database):
    put_profile(client, auth_headers(ca))
    set_status(database, ca, CaVerificationStatus.VERIFIED)

    response = put_profile(client, auth_headers(ca), city="Mumbai", capacity=5)

    assert response.get_json()["verification_status"] == "verified"


@pytest.mark.parametrize(
    "changes", [{"membership_no": "654321"}, {"cop_number": "COP-0001"}], ids=["member", "cop"]
)
def test_new_identity_number_needs_a_new_check(client, ca, auth_headers, database, changes):
    put_profile(client, auth_headers(ca))
    set_status(database, ca, CaVerificationStatus.VERIFIED)

    response = put_profile(client, auth_headers(ca), **changes)

    assert response.get_json()["verification_status"] == "pending"


def test_rejected_profile_goes_back_to_pending_when_saved(client, ca, auth_headers, database):
    put_profile(client, auth_headers(ca))
    set_status(database, ca, CaVerificationStatus.REJECTED)

    response = put_profile(client, auth_headers(ca), about="Fixed my details.")

    assert response.get_json()["verification_status"] == "pending"


def test_membership_number_belongs_to_one_ca(client, make_user, ca, auth_headers):
    put_profile(client, auth_headers(ca))
    other = make_user(role=UserRole.CA)

    response = put_profile(client, auth_headers(other))

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "DUPLICATE_MEMBERSHIP_NO"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("membership_no", "12345"),
        ("membership_no", "12345a"),
        ("cop_number", "   "),
        ("city", ""),
        ("languages", []),
        ("languages", ["klingon"]),
        ("specializations", []),
        ("specializations", ["itr", "gstr_9"]),
        ("capacity", 0),
        ("years_experience", -1),
        ("about", "x" * 501),
    ],
)
def test_invalid_fields_are_rejected(client, ca, auth_headers, field, value):
    response = put_profile(client, auth_headers(ca), **{field: value})

    assert response.status_code == 422
    assert field in response.get_json()["error"]["details"]["json"]


def test_database_rejects_unknown_codes(ca, database):
    # The CHECK constraint guards the array columns even without the API.
    database.session.add(
        CaProfile(user_id=ca.id, **{**PROFILE, "specializations": ["itr", "made_up"]})
    )
    with pytest.raises(IntegrityError, match="ck_ca_profiles_known_specializations"):
        database.session.commit()
    database.session.rollback()


def test_array_filter_uses_contains(client, ca, auth_headers, database):
    put_profile(client, auth_headers(ca))

    found = database.session.execute(
        text("SELECT count(*) FROM ca_profiles WHERE specializations @> ARRAY['itr']::varchar[]")
    ).scalar()

    assert found == 1


@pytest.mark.parametrize("role", [UserRole.BUSINESS, UserRole.ADMIN])
@pytest.mark.parametrize("method", ["get", "put"])
def test_other_roles_are_forbidden(client, make_user, auth_headers, role, method):
    headers = auth_headers(make_user(role=role))

    response = getattr(client, method)(URL, json=PROFILE, headers=headers)

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize("method", ["get", "put"])
def test_requires_login(client, database, method):
    response = getattr(client, method)(URL, json=PROFILE)

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "AUTH_REQUIRED"
