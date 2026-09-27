"""Engagements: a business requests a CA for some filings, and both sides act on it.

MA9   GET  /marketplace/cas/<id>/requestable-filings, POST /marketplace/engagements
MA10  POST /marketplace/engagements/<id>/accept | quote | decline
      POST /marketplace/engagements/<id>/accept-quote | reject-quote | withdraw
MA11  POST /marketplace/engagements/<id>/complete (and filings become "With CA")
MA13  GET  /marketplace/my-engagements, GET /marketplace/ca-engagements
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import (
    Business,
    CaProfile,
    CaService,
    CatalogService,
    ComplianceItem,
    Engagement,
    EngagementItem,
    ObligationTemplate,
)
from app.models.compliance import ComplianceStatus, FilingPath
from app.models.enums import FormCode, UserRole
from app.models.marketplace import CaVerificationStatus, EngagementStatus
from app.models.onboarding import EntityType
from app.seed import seed_service_catalog

BASE = "/api/v1/marketplace"
_numbers = iter(range(100000, 999999))


# --- Fixtures ------------------------------------------------------------------------


@pytest.fixture()
def catalog(legal_rules, database):
    """The seeded service catalog (with form codes), as {code: CatalogService}."""
    seed_service_catalog()
    database.session.commit()
    services = {}
    for service in database.session.query(CatalogService):
        services[service.code] = service
    return services


@pytest.fixture()
def make_business(make_user, database):
    """Create a business user with a registered business; returns (user, business)."""

    def _make_business(name="Asha Traders"):
        owner = make_user(role=UserRole.BUSINESS, full_name="Asha Rao")
        business = Business(
            user_id=owner.id,
            legal_name=name,
            entity_type=EntityType.PROPRIETORSHIP,
            state="Maharashtra",
            address="Pune",
            description="Retail shop",
            annual_turnover=4_500_000,
            investment_amount=800_000,
            pan="ABCDE1234F",
            phone="9876543210",
            gst_registered=True,
            gstin="27ABCDE1234F1Z5",
            deducts_tds=False,
            pays_salary_above_limit=False,
        )
        database.session.add(business)
        database.session.commit()
        return owner, business

    return _make_business


@pytest.fixture()
def add_filing(database, legal_rules):
    """Add one filing (compliance item) to a business."""

    def _add_filing(business, form_code, label, status=ComplianceStatus.UPCOMING, days=20):
        template = database.session.query(ObligationTemplate).filter_by(form_code=form_code).first()
        filing = ComplianceItem(
            business_id=business.id,
            template_id=template.id,
            form_code=form_code,
            fy="2026-27",
            period_label=label,
            period_start=date(2026, 8, 1) + timedelta(days=days),
            period_end=date(2026, 8, 31) + timedelta(days=days),
            due_date=date(2026, 9, 20) + timedelta(days=days),
            status=status,
        )
        database.session.add(filing)
        database.session.commit()
        return filing

    return _add_filing


@pytest.fixture()
def make_ca(make_user, database, catalog):
    """Create a CA (verified unless told otherwise) with prices {service code: price}."""

    def _make_ca(prices=None, status=CaVerificationStatus.VERIFIED, name="Meera Shah"):
        user = make_user(role=UserRole.CA, full_name=name)
        profile = CaProfile(
            user_id=user.id,
            membership_no=str(next(_numbers)),
            cop_number="COP-1",
            city="Pune",
            languages=["english"],
            specializations=["gstr_3b"],
            capacity=10,
            years_experience=5,
            verification_status=status,
        )
        database.session.add(profile)
        database.session.flush()
        for code, price in (prices or {}).items():
            database.session.add(
                CaService(
                    ca_profile_id=profile.id,
                    service_id=catalog[code].id,
                    price=Decimal(price),
                )
            )
        database.session.commit()
        return user, profile

    return _make_ca


@pytest.fixture()
def setup(make_business, add_filing, make_ca, catalog, auth_headers):
    """A business with two GST filings and a CA who prices GSTR-3B and GSTR-1."""
    owner, business = make_business()
    gst_3b = add_filing(business, FormCode.GSTR_3B, "Aug 2026", days=0)
    gst_1 = add_filing(business, FormCode.GSTR_1, "Aug 2026 (GSTR-1)", days=1)
    ca_user, ca = make_ca({"gstr_3b": "800", "gstr_1": "600"})
    return {
        "owner": owner,
        "business": business,
        "business_headers": auth_headers(owner),
        "gst_3b": gst_3b,
        "gst_1": gst_1,
        "ca_user": ca_user,
        "ca": ca,
        "ca_headers": auth_headers(ca_user),
        "catalog": catalog,
    }


def request_body(ca, *pairs):
    """{ca_profile_id, items} for (filing, service) pairs."""
    items = []
    for filing, service in pairs:
        items.append({"compliance_item_id": str(filing.id), "service_id": str(service.id)})
    return {"ca_profile_id": str(ca.id), "items": items}


def send_request(client, s, *pairs, ca=None):
    """Send a request from the setup business; returns the response."""
    body = request_body(ca or s["ca"], *pairs)
    return client.post(f"{BASE}/engagements", json=body, headers=s["business_headers"])


def request_gst(client, s):
    """Request the setup CA for both GST filings; returns the engagement JSON."""
    catalog = s["catalog"]
    response = send_request(
        client, s, (s["gst_3b"], catalog["gstr_3b"]), (s["gst_1"], catalog["gstr_1"])
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def action(client, headers, engagement_id, name, body=None):
    return client.post(f"{BASE}/engagements/{engagement_id}/{name}", json=body, headers=headers)


# --- MA9: the "Request this CA" page -------------------------------------------------


def test_requestable_filings_show_prices_and_why_some_are_blocked(
    client, setup, add_filing, database
):
    business = setup["business"]
    add_filing(business, FormCode.TDS_26Q, "Q2 2026-27", days=2)  # the CA has no 26Q price
    add_filing(business, FormCode.GSTR_3B, "Jul 2026", status=ComplianceStatus.FILED, days=3)

    response = client.get(
        f"{BASE}/cas/{setup['ca'].id}/requestable-filings", headers=setup["business_headers"]
    )

    assert response.status_code == 200
    rows = {row["period_label"]: row for row in response.get_json()}
    assert rows["Aug 2026"]["blocked_reason"] is None
    assert rows["Aug 2026"]["options"][0]["price"] == "800.00"
    assert rows["Aug 2026"]["options"][0]["name"] == "GSTR-3B filing"
    assert rows["Q2 2026-27"]["blocked_reason"] == "This CA has not listed a price for this filing."
    assert rows["Jul 2026"]["blocked_reason"] == "Already filed."


def test_a_requested_filing_is_blocked_for_every_ca(client, setup, make_ca):
    request_gst(client, setup)
    _, other_ca = make_ca({"gstr_3b": "700"}, name="Other CA")

    response = client.get(
        f"{BASE}/cas/{other_ca.id}/requestable-filings", headers=setup["business_headers"]
    )

    row = response.get_json()[0]
    assert row["period_label"] == "Aug 2026"
    assert row["blocked_reason"] == "Already requested from a CA or with a CA."


def test_itr_filing_offers_every_itr_service_of_the_ca(client, setup, add_filing, make_ca):
    add_filing(setup["business"], FormCode.ITR, "FY 2025-26", days=30)
    _, ca = make_ca({"itr_presumptive": "1200", "itr_business": "2500"}, name="ITR CA")

    response = client.get(
        f"{BASE}/cas/{ca.id}/requestable-filings", headers=setup["business_headers"]
    )

    rows = {row["period_label"]: row for row in response.get_json()}
    names = [option["name"] for option in rows["FY 2025-26"]["options"]]
    assert names == [
        "ITR filing: presumptive income (ITR-4)",
        "ITR filing: business or profession (ITR-3)",
    ]


def test_requestable_filings_need_a_registered_business(client, make_user, auth_headers, setup):
    headers = auth_headers(make_user(role=UserRole.BUSINESS))

    response = client.get(f"{BASE}/cas/{setup['ca'].id}/requestable-filings", headers=headers)

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "BUSINESS_NOT_FOUND"


# --- MA9: sending a request ----------------------------------------------------------


def test_sending_a_request(client, setup, mailbox, database):
    engagement = request_gst(client, setup)

    assert engagement["status"] == "requested"
    assert engagement["ca_name"] == "Meera Shah"
    assert engagement["business_name"] == "Asha Traders"
    prices = [(item["period_label"], item["listed_price"]) for item in engagement["items"]]
    assert prices == [("Aug 2026", "800.00"), ("Aug 2026 (GSTR-1)", "600.00")]
    assert engagement["items"][0]["agreed_price"] is None

    row = database.session.get(Engagement, uuid.UUID(engagement["id"]))
    assert row.expires_at - row.requested_at == timedelta(hours=48)

    # The CA is told by email.
    assert len(mailbox) == 1
    assert mailbox[0]["To"] == setup["ca_user"].email
    assert "Asha Traders" in mailbox[0].get_content()


def test_listed_price_is_kept_when_the_ca_changes_the_menu(client, setup, database):
    engagement = request_gst(client, setup)
    menu_row = database.session.query(CaService).filter_by(ca_profile_id=setup["ca"].id).first()
    menu_row.price = Decimal("9999")
    database.session.commit()

    rows = client.get(f"{BASE}/my-engagements", headers=setup["business_headers"]).get_json()

    assert rows[0]["id"] == engagement["id"]
    assert {item["listed_price"] for item in rows[0]["items"]} == {"800.00", "600.00"}


def test_a_filing_cannot_be_in_two_open_engagements(client, setup, make_ca):
    request_gst(client, setup)
    _, other_ca = make_ca({"gstr_3b": "700"}, name="Other CA")

    response = send_request(
        client, setup, (setup["gst_3b"], setup["catalog"]["gstr_3b"]), ca=other_ca
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "FILING_ALREADY_REQUESTED"


@pytest.mark.parametrize("how", ["declined", "withdrawn"])
def test_a_filing_is_free_again_after_the_request_ends(client, setup, how):
    engagement = request_gst(client, setup)
    if how == "declined":
        action(client, setup["ca_headers"], engagement["id"], "decline")
    else:
        action(client, setup["business_headers"], engagement["id"], "withdraw")

    response = send_request(client, setup, (setup["gst_3b"], setup["catalog"]["gstr_3b"]))

    assert response.status_code == 201


def test_request_errors(client, setup, make_business, add_filing, make_ca):
    s = setup
    catalog = s["catalog"]
    _, other_business = make_business("Someone Else")
    others_filing = add_filing(other_business, FormCode.GSTR_3B, "Aug 2026")
    filed = add_filing(s["business"], FormCode.GSTR_3B, "Jul 2026", ComplianceStatus.FILED, 5)
    _, pending_ca = make_ca({"gstr_3b": "500"}, status=CaVerificationStatus.PENDING)

    def code_of(response):
        return response.status_code, response.get_json()["error"]["code"]

    gst = (s["gst_3b"], catalog["gstr_3b"])
    assert code_of(send_request(client, s, gst, gst)) == (400, "DUPLICATE_FILING")
    assert code_of(send_request(client, s, (others_filing, catalog["gstr_3b"]))) == (
        404,
        "FILING_NOT_FOUND",
    )
    assert code_of(send_request(client, s, (filed, catalog["gstr_3b"]))) == (
        409,
        "FILING_ALREADY_FILED",
    )
    # GSTR-1 service for a GSTR-3B filing, and a service the CA does not offer.
    assert code_of(send_request(client, s, (s["gst_3b"], catalog["gstr_1"]))) == (
        400,
        "SERVICE_NOT_OFFERED",
    )
    assert code_of(send_request(client, s, (s["gst_3b"], catalog["cmp_08"]))) == (
        400,
        "SERVICE_NOT_OFFERED",
    )
    assert code_of(send_request(client, s, gst, ca=pending_ca)) == (404, "CA_NOT_FOUND")

    empty = client.post(
        f"{BASE}/engagements",
        json={"ca_profile_id": str(s["ca"].id), "items": []},
        headers=s["business_headers"],
    )
    assert empty.status_code == 422


# --- MA10: the CA answers ------------------------------------------------------------


def test_ca_accepts_at_the_listed_prices(client, setup, mailbox, database):
    engagement = request_gst(client, setup)
    mailbox.clear()

    response = action(client, setup["ca_headers"], engagement["id"], "accept")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "active"
    assert [item["agreed_price"] for item in body["items"]] == ["800.00", "600.00"]
    assert body["activated_at"] is not None
    # MA11: the filings are now "With CA".
    database.session.expire_all()
    for filing in [setup["gst_3b"], setup["gst_1"]]:
        row = database.session.get(ComplianceItem, filing.id)
        assert row.status == ComplianceStatus.WITH_CA
        assert row.filing_path == FilingPath.CA
    # The business is told by email.
    assert mailbox[0]["To"] == setup["owner"].email
    assert "accepted" in mailbox[0].get_content()


def test_ca_sends_a_quote_and_the_business_accepts_it(client, setup, mailbox, database):
    engagement = request_gst(client, setup)
    mailbox.clear()
    item_ids = [item["id"] for item in engagement["items"]]
    quote = {
        "reason": "Your August has 400 invoices, more work than usual.",
        "prices": [
            {"engagement_item_id": item_ids[0], "price": "1200"},
            {"engagement_item_id": item_ids[1], "price": "900"},
        ],
    }

    quoted = action(client, setup["ca_headers"], engagement["id"], "quote", quote).get_json()

    assert quoted["status"] == "quoted"
    assert quoted["quote_reason"] == quote["reason"]
    assert [item["quoted_price"] for item in quoted["items"]] == ["1200.00", "900.00"]
    assert "400 invoices" in mailbox[0].get_content()
    # The filings are not "With CA" yet.
    database.session.expire_all()
    assert database.session.get(ComplianceItem, setup["gst_3b"].id).status == "upcoming"

    accepted = action(client, setup["business_headers"], engagement["id"], "accept-quote")

    assert accepted.get_json()["status"] == "active"
    assert [item["agreed_price"] for item in accepted.get_json()["items"]] == [
        "1200.00",
        "900.00",
    ]
    database.session.expire_all()
    assert database.session.get(ComplianceItem, setup["gst_3b"].id).status == "with_ca"


def test_business_rejects_a_quote(client, setup):
    engagement = request_gst(client, setup)
    prices = []
    for item in engagement["items"]:
        prices.append({"engagement_item_id": item["id"], "price": "5000"})
    body = {"reason": "Too much work.", "prices": prices}
    action(client, setup["ca_headers"], engagement["id"], "quote", body)

    response = action(client, setup["business_headers"], engagement["id"], "reject-quote")

    assert response.get_json()["status"] == "cancelled"
    # The filings are free for another CA.
    again = send_request(client, setup, (setup["gst_3b"], setup["catalog"]["gstr_3b"]))
    assert again.status_code == 201


def test_a_quote_needs_a_reason_and_every_price(client, setup):
    engagement = request_gst(client, setup)
    first_item = engagement["items"][0]["id"]

    blank_reason = {"reason": "  ", "prices": [{"engagement_item_id": first_item, "price": "1"}]}
    one_price = {
        "reason": "Busy month.",
        "prices": [{"engagement_item_id": first_item, "price": "1"}],
    }

    assert (
        action(client, setup["ca_headers"], engagement["id"], "quote", blank_reason).status_code
        == 422
    )
    response = action(client, setup["ca_headers"], engagement["id"], "quote", one_price)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "QUOTE_INCOMPLETE"


def test_ca_declines(client, setup, mailbox):
    engagement = request_gst(client, setup)
    mailbox.clear()

    response = action(client, setup["ca_headers"], engagement["id"], "decline")

    assert response.get_json()["status"] == "declined"
    assert "declined" in mailbox[0].get_content()


def test_business_withdraws_an_unanswered_request(client, setup):
    engagement = request_gst(client, setup)

    response = action(client, setup["business_headers"], engagement["id"], "withdraw")

    assert response.get_json()["status"] == "cancelled"


# --- MA11: the rest of the lifecycle ---------------------------------------------------


def test_ca_marks_an_active_engagement_completed(client, setup):
    engagement = request_gst(client, setup)
    action(client, setup["ca_headers"], engagement["id"], "accept")

    response = action(client, setup["ca_headers"], engagement["id"], "complete")

    assert response.get_json()["status"] == "completed"
    assert response.get_json()["completed_at"] is not None


@pytest.mark.parametrize(
    ("first", "then", "who"),
    [
        ("accept", "accept", "ca"),  # already active
        ("accept", "decline", "ca"),
        ("accept", "withdraw", "business"),  # too late to withdraw
        ("decline", "accept", "ca"),
        (None, "complete", "ca"),  # not active yet
        (None, "accept-quote", "business"),  # no quote was sent
    ],
)
def test_actions_only_work_from_the_right_status(client, setup, first, then, who):
    engagement = request_gst(client, setup)
    if first:
        action(client, setup["ca_headers"], engagement["id"], first)
    headers = setup["ca_headers"] if who == "ca" else setup["business_headers"]

    response = action(client, headers, engagement["id"], then)

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "INVALID_STATUS"


def test_nobody_else_can_act_on_an_engagement(client, setup, make_ca, make_business, auth_headers):
    engagement = request_gst(client, setup)
    other_ca_user, _ = make_ca({"gstr_3b": "700"}, name="Other CA")
    other_owner, _ = make_business("Someone Else")

    by_other_ca = action(client, auth_headers(other_ca_user), engagement["id"], "accept")
    by_other_business = action(client, auth_headers(other_owner), engagement["id"], "withdraw")
    by_wrong_role = action(client, setup["business_headers"], engagement["id"], "accept")
    unknown = action(client, setup["ca_headers"], uuid.uuid4(), "accept")

    assert by_other_ca.status_code == 404
    assert by_other_business.status_code == 404
    assert by_wrong_role.status_code == 403
    assert unknown.status_code == 404


# --- MA13: each side's list of engagements ---------------------------------------------


def test_each_side_sees_only_its_own_engagements(
    client, setup, make_business, add_filing, make_ca, auth_headers
):
    mine = request_gst(client, setup)
    # Another business requests another CA.
    other_owner, other_business = make_business("Someone Else")
    other_filing = add_filing(other_business, FormCode.GSTR_3B, "Aug 2026")
    other_ca_user, other_ca = make_ca({"gstr_3b": "700"}, name="Other CA")
    client.post(
        f"{BASE}/engagements",
        json=request_body(other_ca, (other_filing, setup["catalog"]["gstr_3b"])),
        headers=auth_headers(other_owner),
    )

    business_list = client.get(f"{BASE}/my-engagements", headers=setup["business_headers"])
    ca_list = client.get(f"{BASE}/ca-engagements", headers=setup["ca_headers"])

    assert [row["id"] for row in business_list.get_json()] == [mine["id"]]
    assert [row["id"] for row in ca_list.get_json()] == [mine["id"]]


def test_a_ca_without_a_profile_has_no_engagements(client, make_user, auth_headers, database):
    headers = auth_headers(make_user(role=UserRole.CA))

    response = client.get(f"{BASE}/ca-engagements", headers=headers)

    assert response.status_code == 200
    assert response.get_json() == []


@pytest.mark.parametrize(
    ("url", "allowed"),
    [("/my-engagements", UserRole.BUSINESS), ("/ca-engagements", UserRole.CA)],
)
def test_lists_are_for_their_role_only(client, make_user, auth_headers, database, url, allowed):
    for role in UserRole:
        if role == allowed:
            continue
        response = client.get(BASE + url, headers=auth_headers(make_user(role=role)))
        assert response.status_code == 403


def test_engagement_rows_are_stored(client, setup, database):
    engagement = request_gst(client, setup)

    rows = database.session.query(EngagementItem).filter_by(
        engagement_id=uuid.UUID(engagement["id"])
    )

    assert rows.count() == 2
    assert database.session.get(Engagement, uuid.UUID(engagement["id"])).status == (
        EngagementStatus.REQUESTED
    )
