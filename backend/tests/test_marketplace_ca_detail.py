"""GET /api/v1/marketplace/cas/<id>: one verified CA's page, with their services and prices."""

import uuid
from decimal import Decimal

import pytest

from app.models import CaProfile, CaService, CatalogService
from app.models.base import utcnow
from app.models.enums import UserRole
from app.models.marketplace import CaVerificationStatus, ServiceUnit

_numbers = iter(range(100000, 999999))


def url(profile_id):
    return f"/api/v1/marketplace/cas/{profile_id}"


@pytest.fixture()
def business_headers(make_user, auth_headers):
    return auth_headers(make_user(role=UserRole.BUSINESS))


@pytest.fixture()
def service(database):
    """Make a catalog service: service("gstr_3b", sort_order=2)."""

    def _service(code, sort_order=1, is_active=True):
        row = CatalogService(
            code=code,
            name=code.upper(),
            description="A service.",
            unit=ServiceUnit.PER_RETURN,
            sort_order=sort_order,
            is_active=is_active,
        )
        database.session.add(row)
        database.session.commit()
        return row

    return _service


@pytest.fixture()
def add_ca(make_user, database):
    """Create a CA with a profile (verified unless told otherwise) and prices."""

    def _add_ca(prices=None, status=CaVerificationStatus.VERIFIED, user_fields=None):
        user = make_user(role=UserRole.CA, full_name="Meera Shah", **(user_fields or {}))
        profile = CaProfile(
            user_id=user.id,
            membership_no=str(next(_numbers)),
            cop_number="COP-SECRET",
            city="Pune",
            languages=["english", "marathi"],
            specializations=["gstr_3b"],
            capacity=10,
            years_experience=7,
            about="GST for traders.",
            verification_status=status,
        )
        database.session.add(profile)
        database.session.flush()
        for catalog_service, price in (prices or {}).items():
            database.session.add(
                CaService(
                    ca_profile_id=profile.id, service_id=catalog_service.id, price=Decimal(price)
                )
            )
        database.session.commit()
        return profile

    return _add_ca


def test_shows_the_public_profile(client, business_headers, add_ca):
    profile = add_ca()

    response = client.get(url(profile.id), headers=business_headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["full_name"] == "Meera Shah"
    assert body["city"] == "Pune"
    assert body["languages"] == ["english", "marathi"]
    assert body["years_experience"] == 7
    assert body["services"] == []
    assert "cop_number" not in body
    assert "capacity" not in body


def test_lists_offered_services_in_catalog_order_with_ranges(
    client, business_headers, add_ca, service, database
):
    itr = service("itr", sort_order=1)
    gst = service("gstr_3b", sort_order=2)
    unused = service("tax_audit", sort_order=3)
    dropped = service("gstr_1", sort_order=4)
    profile = add_ca({gst: "650", itr: "1500", dropped: "400"})
    # Two more CAs make three for GSTR-3B, so its range is known.
    add_ca({gst: "600"})
    add_ca({gst: "1000"})
    row = database.session.query(CaService).filter_by(service_id=dropped.id).one()
    row.is_active = False  # the CA stopped offering GSTR-1
    database.session.commit()

    services = client.get(url(profile.id), headers=business_headers).get_json()["services"]

    assert [s["code"] for s in services] == ["itr", "gstr_3b"]  # not tax_audit, not gstr_1
    assert unused.code not in [s["code"] for s in services]
    gst_row = services[1]
    assert gst_row["price"] == "650.00"
    assert (gst_row["min_price"], gst_row["median_price"], gst_row["max_price"]) == (
        "600.00",
        "650.00",
        "1000.00",
    )
    assert services[0]["median_price"] is None  # only one CA offers ITR


def test_hides_services_removed_from_the_catalog(client, business_headers, add_ca, service):
    retired = service("old_service", is_active=False)
    profile = add_ca({retired: "500"})

    services = client.get(url(profile.id), headers=business_headers).get_json()["services"]

    assert services == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": CaVerificationStatus.PENDING},
        {"status": CaVerificationStatus.REJECTED},
        {"user_fields": {"is_active": False}},
        {"user_fields": {"deleted_at": utcnow()}},
    ],
    ids=["pending", "rejected", "deactivated", "deleted"],
)
def test_unlisted_cas_are_not_found(client, business_headers, add_ca, kwargs):
    profile = add_ca(**kwargs)

    response = client.get(url(profile.id), headers=business_headers)

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "CA_NOT_FOUND"


def test_unknown_id_is_not_found(client, business_headers, database):
    assert client.get(url(uuid.uuid4()), headers=business_headers).status_code == 404
    assert client.get(url("not-a-uuid"), headers=business_headers).status_code == 404


@pytest.mark.parametrize("role", [UserRole.CA, UserRole.ADMIN])
def test_other_roles_are_forbidden(client, make_user, auth_headers, add_ca, role):
    profile = add_ca()

    response = client.get(url(profile.id), headers=auth_headers(make_user(role=role)))

    assert response.status_code == 403


def test_requires_login(client, add_ca):
    assert client.get(url(add_ca().id)).status_code == 401
