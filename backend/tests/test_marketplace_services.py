"""The service catalog, CA price menus and the typical price range (MA5, MA6).

GET /api/v1/marketplace/services       catalog + min / median / max price
GET /api/v1/marketplace/ca-services    the CA's own price menu
PUT /api/v1/marketplace/ca-services    replace it
GET /api/v1/marketplace/cas?service=   CAs offering a service, with their price
"""

import uuid
from decimal import Decimal

import pytest

from app.models import CaProfile, CaService, CatalogService
from app.models.base import utcnow
from app.models.enums import UserRole
from app.models.marketplace import CaVerificationStatus, ServiceUnit

SERVICES_URL = "/api/v1/marketplace/services"
MENU_URL = "/api/v1/marketplace/ca-services"
CAS_URL = "/api/v1/marketplace/cas"

_numbers = iter(range(100000, 999999))


@pytest.fixture()
def catalog(database):
    """Two catalog services and one retired one. Returns {code: CatalogService}."""
    services = {
        "gstr_3b": CatalogService(
            code="gstr_3b",
            name="GSTR-3B filing",
            description="Summary GST return.",
            unit=ServiceUnit.PER_RETURN,
            sort_order=2,
        ),
        "itr_business": CatalogService(
            code="itr_business",
            name="ITR filing: business",
            description="ITR-3.",
            unit=ServiceUnit.PER_RETURN,
            sort_order=1,
        ),
        "retired": CatalogService(
            code="retired",
            name="Old service",
            description="No longer offered.",
            unit=ServiceUnit.ONE_TIME,
            sort_order=3,
            is_active=False,
        ),
    }
    for service in services.values():
        database.session.add(service)
    database.session.commit()
    return services


@pytest.fixture()
def add_ca(make_user, database):
    """Create a CA with a profile (verified unless told otherwise) and some prices."""

    def _add_ca(prices=None, status=CaVerificationStatus.VERIFIED, user_fields=None, name="CA"):
        user = make_user(role=UserRole.CA, full_name=name, **(user_fields or {}))
        profile = CaProfile(
            user_id=user.id,
            membership_no=str(next(_numbers)),
            cop_number="COP-1",
            city="Pune",
            languages=["english"],
            specializations=["itr"],
            capacity=10,
            years_experience=5,
            verification_status=status,
        )
        database.session.add(profile)
        database.session.flush()
        for service, price in (prices or {}).items():
            database.session.add(
                CaService(ca_profile_id=profile.id, service_id=service.id, price=Decimal(price))
            )
        database.session.commit()
        return user

    return _add_ca


def get_services(client, headers):
    response = client.get(SERVICES_URL, headers=headers)
    assert response.status_code == 200
    return {row["code"]: row for row in response.get_json()}


# --- Catalog and typical price range -----------------------------------------------


@pytest.mark.parametrize("role", list(UserRole))
def test_every_role_sees_the_active_catalog_in_order(
    client, make_user, auth_headers, catalog, role
):
    response = client.get(SERVICES_URL, headers=auth_headers(make_user(role=role)))

    assert response.status_code == 200
    assert [row["code"] for row in response.get_json()] == ["itr_business", "gstr_3b"]
    assert response.get_json()[0]["unit"] == "per_return"


def test_range_needs_three_cas(client, make_user, auth_headers, catalog, add_ca):
    gst = catalog["gstr_3b"]
    add_ca({gst: "500"})
    add_ca({gst: "900"})
    headers = auth_headers(make_user())

    row = get_services(client, headers)["gstr_3b"]
    assert row["ca_count"] == 2
    assert row["min_price"] is None
    assert row["median_price"] is None

    add_ca({gst: "700"})
    row = get_services(client, headers)["gstr_3b"]
    assert row["ca_count"] == 3
    assert (row["min_price"], row["median_price"], row["max_price"]) == (
        "500.00",
        "700.00",
        "900.00",
    )


def test_median_of_an_even_count_is_the_middle_two_averaged(
    client, make_user, auth_headers, catalog, add_ca
):
    gst = catalog["gstr_3b"]
    for price in ["400", "500", "900", "5000"]:
        add_ca({gst: price})

    row = get_services(client, auth_headers(make_user()))["gstr_3b"]

    assert row["median_price"] == "700.00"  # (500 + 900) / 2, not pulled up by 5000


def test_range_counts_only_listed_cas_and_current_prices(
    client, make_user, auth_headers, catalog, add_ca, database
):
    gst = catalog["gstr_3b"]
    for price in ["500", "600", "700"]:
        add_ca({gst: price})
    add_ca({gst: "1"}, status=CaVerificationStatus.PENDING)
    add_ca({gst: "1"}, status=CaVerificationStatus.REJECTED)
    add_ca({gst: "1"}, user_fields={"is_active": False})
    add_ca({gst: "1"}, user_fields={"deleted_at": utcnow()})
    dropped = add_ca({gst: "1"})
    row = database.session.query(CaService).join(CaProfile).filter_by(user_id=dropped.id).one()
    row.is_active = False
    database.session.commit()

    row = get_services(client, auth_headers(make_user()))["gstr_3b"]

    assert row["ca_count"] == 3
    assert row["min_price"] == "500.00"


def test_catalog_requires_login(client, database):
    assert client.get(SERVICES_URL).status_code == 401


# --- The CA's price menu -------------------------------------------------------------


def test_menu_is_empty_before_any_price(client, make_user, auth_headers, database):
    ca = make_user(role=UserRole.CA)  # no profile yet either

    response = client.get(MENU_URL, headers=auth_headers(ca))

    assert response.status_code == 200
    assert response.get_json() == {"items": []}


def test_saving_the_menu(client, auth_headers, catalog, add_ca):
    ca = add_ca()
    gst, itr = catalog["gstr_3b"], catalog["itr_business"]
    body = {
        "items": [
            {"service_id": str(gst.id), "price": "750"},
            {"service_id": str(itr.id), "price": "2500.50"},
        ]
    }

    response = client.put(MENU_URL, json=body, headers=auth_headers(ca))

    assert response.status_code == 200
    saved = {item["service_id"]: item["price"] for item in response.get_json()["items"]}
    assert saved == {str(gst.id): "750.00", str(itr.id): "2500.50"}
    assert client.get(MENU_URL, headers=auth_headers(ca)).get_json() == response.get_json()


def test_saving_again_replaces_the_menu(client, auth_headers, catalog, add_ca, database):
    gst, itr = catalog["gstr_3b"], catalog["itr_business"]
    ca = add_ca({gst: "500", itr: "2000"})

    # Drop GSTR-3B, change the ITR price.
    body = {"items": [{"service_id": str(itr.id), "price": "2200"}]}
    response = client.put(MENU_URL, json=body, headers=auth_headers(ca))

    assert response.get_json()["items"] == [{"service_id": str(itr.id), "price": "2200.00"}]
    dropped = database.session.query(CaService).filter_by(service_id=gst.id).one()
    assert dropped.is_active is False  # soft-deleted, not removed
    assert dropped.deleted_at is not None

    # Offering it again brings the same row back.
    body["items"].append({"service_id": str(gst.id), "price": "550"})
    client.put(MENU_URL, json=body, headers=auth_headers(ca))

    database.session.expire_all()
    rows = database.session.query(CaService).filter_by(service_id=gst.id).all()
    assert len(rows) == 1
    assert rows[0].is_active is True
    assert rows[0].deleted_at is None
    assert rows[0].price == Decimal("550.00")


def test_an_empty_menu_offers_nothing(client, auth_headers, catalog, add_ca):
    ca = add_ca({catalog["gstr_3b"]: "500"})

    response = client.put(MENU_URL, json={"items": []}, headers=auth_headers(ca))

    assert response.get_json() == {"items": []}


def test_saving_needs_a_profile(client, make_user, auth_headers, catalog):
    ca = make_user(role=UserRole.CA)
    body = {"items": [{"service_id": str(catalog["gstr_3b"].id), "price": "500"}]}

    response = client.put(MENU_URL, json=body, headers=auth_headers(ca))

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "CA_PROFILE_NOT_FOUND"


@pytest.mark.parametrize("which", ["retired", "made_up"])
def test_only_active_catalog_services_can_be_priced(client, auth_headers, catalog, add_ca, which):
    service_id = catalog["retired"].id if which == "retired" else uuid.uuid4()
    body = {"items": [{"service_id": str(service_id), "price": "500"}]}

    response = client.put(MENU_URL, json=body, headers=auth_headers(add_ca()))

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "UNKNOWN_SERVICE"


@pytest.mark.parametrize("price", ["0", "-5", "1000001", "abc"])
def test_invalid_prices_are_rejected(client, auth_headers, catalog, add_ca, price):
    body = {"items": [{"service_id": str(catalog["gstr_3b"].id), "price": price}]}

    response = client.put(MENU_URL, json=body, headers=auth_headers(add_ca()))

    assert response.status_code == 422


@pytest.mark.parametrize("role", [UserRole.BUSINESS, UserRole.ADMIN])
@pytest.mark.parametrize("method", ["get", "put"])
def test_menu_is_for_cas_only(client, make_user, auth_headers, role, method):
    headers = auth_headers(make_user(role=role))

    response = getattr(client, method)(MENU_URL, json={"items": []}, headers=headers)

    assert response.status_code == 403


# --- "Find a CA" filtered by a service ------------------------------------------------


def test_ca_list_filtered_by_service_shows_each_price(
    client, make_user, auth_headers, catalog, add_ca
):
    gst, itr = catalog["gstr_3b"], catalog["itr_business"]
    add_ca({gst: "650"}, name="GST CA")
    add_ca({itr: "2000"}, name="ITR CA")
    headers = auth_headers(make_user(role=UserRole.BUSINESS))

    filtered = client.get(f"{CAS_URL}?service=gstr_3b", headers=headers).get_json()
    everyone = client.get(CAS_URL, headers=headers).get_json()

    assert [(i["full_name"], i["price"]) for i in filtered["items"]] == [("GST CA", "650.00")]
    assert {i["price"] for i in everyone["items"]} == {None}  # no service chosen
    assert everyone["total"] == 2
