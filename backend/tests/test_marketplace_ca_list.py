"""GET /api/v1/marketplace/cas: the verified CAs a business can browse."""

import pytest

from app.models import CaProfile
from app.models.base import utcnow
from app.models.enums import UserRole
from app.models.marketplace import CaVerificationStatus

URL = "/api/v1/marketplace/cas"

_numbers = iter(range(100000, 999999))


@pytest.fixture()
def business(make_user):
    return make_user(role=UserRole.BUSINESS)


@pytest.fixture()
def add_ca(make_user, database):
    """Create a CA user with a profile; verified unless told otherwise."""

    def _add_ca(
        full_name="Test CA",
        status=CaVerificationStatus.VERIFIED,
        user_fields=None,
        **profile_fields,
    ):
        user = make_user(role=UserRole.CA, full_name=full_name, **(user_fields or {}))
        fields = {
            "membership_no": str(next(_numbers)),
            "cop_number": "COP-1",
            "city": "Pune",
            "languages": ["english"],
            "specializations": ["itr"],
            "capacity": 10,
            "years_experience": 5,
            **profile_fields,
        }
        database.session.add(CaProfile(user_id=user.id, verification_status=status, **fields))
        database.session.commit()
        return user

    return _add_ca


def names(response):
    return [item["full_name"] for item in response.get_json()["items"]]


def test_lists_only_verified_cas_with_live_accounts(client, business, auth_headers, add_ca):
    add_ca("Verified CA")
    add_ca("Pending CA", status=CaVerificationStatus.PENDING)
    add_ca("Rejected CA", status=CaVerificationStatus.REJECTED)
    add_ca("Deactivated CA", user_fields={"is_active": False})
    add_ca("Deleted CA", user_fields={"deleted_at": utcnow()})

    response = client.get(URL, headers=auth_headers(business))

    assert response.status_code == 200
    assert names(response) == ["Verified CA"]


def test_item_shows_public_fields_only(client, business, auth_headers, add_ca):
    add_ca("Meera Shah", membership_no="123456", about="GST help.")

    item = client.get(URL, headers=auth_headers(business)).get_json()["items"][0]

    assert item["full_name"] == "Meera Shah"
    assert item["membership_no"] == "123456"
    assert item["about"] == "GST help."
    assert "cop_number" not in item
    assert "capacity" not in item


def test_most_experienced_first(client, business, auth_headers, add_ca):
    add_ca("Junior", years_experience=2)
    add_ca("Senior", years_experience=20)

    response = client.get(URL, headers=auth_headers(business))

    assert names(response) == ["Senior", "Junior"]


def test_filters(client, business, auth_headers, add_ca):
    add_ca("GST Pune", specializations=["gstr_1", "gstr_3b"], city="Pune", languages=["marathi"])
    add_ca("ITR Mumbai", specializations=["itr"], city="Navi Mumbai", languages=["hindi"])

    def get(query):
        return names(client.get(f"{URL}?{query}", headers=auth_headers(business)))

    assert get("specialization=gstr_3b") == ["GST Pune"]
    assert get("language=hindi") == ["ITR Mumbai"]
    assert get("city=mumbai") == ["ITR Mumbai"]  # any case, part of the name
    assert get("specialization=itr&city=pune") == []


def test_pagination(client, business, auth_headers, add_ca):
    for years in range(5):
        add_ca(f"CA {years}", years_experience=years)

    body = client.get(f"{URL}?page=2&page_size=2", headers=auth_headers(business)).get_json()

    assert [item["full_name"] for item in body["items"]] == ["CA 2", "CA 1"]
    assert (body["page"], body["page_size"], body["total"]) == (2, 2, 5)


@pytest.mark.parametrize(
    "query", ["specialization=gstr_9", "language=klingon", "page=0", "page_size=101"]
)
def test_invalid_filters_are_rejected(client, business, auth_headers, query):
    response = client.get(f"{URL}?{query}", headers=auth_headers(business))

    assert response.status_code == 422


@pytest.mark.parametrize("role", [UserRole.CA, UserRole.ADMIN])
def test_other_roles_are_forbidden(client, make_user, auth_headers, role):
    response = client.get(URL, headers=auth_headers(make_user(role=role)))

    assert response.status_code == 403


def test_requires_login(client, database):
    assert client.get(URL).status_code == 401
