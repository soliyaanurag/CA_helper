"""Engagements: a business requests a CA for some filings, and both sides act on it.

MA9   GET  /marketplace/cas/<id>/requestable-filings, POST /marketplace/engagements
MA10  POST /marketplace/engagements/<id>/accept | quote | decline
      POST /marketplace/engagements/<id>/accept-quote | reject-quote | withdraw
MA11  POST /marketplace/engagements/<id>/complete (and filings become "With CA")
MA13  GET  /marketplace/my-engagements, GET /marketplace/ca-engagements
AL1   every engagement event also adds a tray entry (alerts_service.notify)
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from flask_jwt_extended import verify_jwt_in_request

from app.errors import ApiError
from app.models import (
    Business,
    CaProfile,
    CaService,
    CatalogService,
    ComplianceItem,
    ComplianceItemDocument,
    Document,
    Engagement,
    EngagementItem,
    Notification,
    ObligationTemplate,
    Rating,
    RegulatoryProfile,
)
from app.models.base import utcnow
from app.models.compliance import ComplianceStatus, FilingPath
from app.models.documents import DocumentType
from app.models.enums import FormCode, UserRole
from app.models.marketplace import CaVerificationStatus, EngagementStatus
from app.models.onboarding import EntityType, GstScheme, ItrForm, MsmeTier
from app.seed import seed_service_catalog
from app.services import marketplace_service
from app.utils.decorators import require_ca_access
from worker import build_scheduler

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


# ITR: an ITR filing is priced only with the service for the business's own ITR form.
ITR_PRICES = {"itr_presumptive": "1200", "itr_business": "2500", "itr_firm_company": "8000"}


def give_profile(database, business, itr_form):
    """Give the business a regulatory profile with this ITR form."""
    database.session.add(
        RegulatoryProfile(
            business_id=business.id,
            msme_tier=MsmeTier.MICRO,
            gst_scheme=GstScheme.REGULAR_MONTHLY,
            gst_registration_suggested=False,
            itr_form=itr_form,
            presumptive_eligible=False,
            audit_applicable=False,
            files_24q=False,
            files_26q=False,
            roc_not_tracked=False,
            explanations={},
            rule_version="test",
            computed_at=utcnow(),
        )
    )
    database.session.commit()


def itr_options(client, setup, ca):
    response = client.get(
        f"{BASE}/cas/{ca.id}/requestable-filings", headers=setup["business_headers"]
    )
    rows = {row["period_label"]: row for row in response.get_json()}
    return rows["FY 2025-26"]


@pytest.mark.parametrize(
    ("itr_form", "service_code"),
    [
        (ItrForm.ITR_3, "itr_business"),
        (ItrForm.ITR_4, "itr_presumptive"),
        (ItrForm.ITR_5, "itr_firm_company"),
        (ItrForm.ITR_6, "itr_firm_company"),
    ],
)
def test_an_itr_filing_gets_only_the_service_of_its_itr_form(
    client, setup, add_filing, make_ca, database, itr_form, service_code
):
    give_profile(database, setup["business"], itr_form)
    itr = add_filing(setup["business"], FormCode.ITR, "FY 2025-26", days=30)
    _, ca = make_ca(ITR_PRICES, name="ITR CA")
    service = setup["catalog"][service_code]

    row = itr_options(client, setup, ca)
    response = send_request(client, setup, (itr, service), ca=ca)

    assert [option["name"] for option in row["options"]] == [service.name]
    assert response.status_code == 201
    stored = database.session.query(EngagementItem).filter_by(compliance_item_id=itr.id).one()
    assert stored.service_id == service.id


def test_an_llp_cannot_request_the_presumptive_itr_service(
    client, setup, add_filing, make_ca, database
):
    give_profile(database, setup["business"], ItrForm.ITR_5)
    itr = add_filing(setup["business"], FormCode.ITR, "FY 2025-26", days=30)
    _, ca = make_ca(ITR_PRICES, name="ITR CA")

    response = send_request(client, setup, (itr, setup["catalog"]["itr_presumptive"]), ca=ca)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "SERVICE_NOT_OFFERED"


def test_an_itr_filing_is_blocked_when_the_ca_lacks_the_right_service(
    client, setup, add_filing, make_ca, database
):
    give_profile(database, setup["business"], ItrForm.ITR_5)
    add_filing(setup["business"], FormCode.ITR, "FY 2025-26", days=30)
    _, ca = make_ca({"itr_presumptive": "1200"}, name="Presumptive only")

    row = itr_options(client, setup, ca)

    assert row["options"] == []
    assert row["blocked_reason"] == (
        "This CA has not listed a price for the ITR of your business type."
    )


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


# --- Data isolation: nobody reaches another business's or CA's engagement ---------------


def quote_body(engagement):
    prices = [{"engagement_item_id": item["id"], "price": "900"} for item in engagement["items"]]
    return {"reason": "More invoices than usual.", "prices": prices}


@pytest.mark.parametrize("name", ["accept", "quote", "decline", "complete"])
def test_another_ca_cannot_act_on_an_engagement(client, setup, make_ca, auth_headers, name):
    engagement = request_gst(client, setup)
    if name == "complete":
        action(client, setup["ca_headers"], engagement["id"], "accept")
    other_ca_user, _ = make_ca({"gstr_3b": "700"}, name="Other CA")
    body = quote_body(engagement) if name == "quote" else None

    response = action(client, auth_headers(other_ca_user), engagement["id"], name, body)

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "ENGAGEMENT_NOT_FOUND"


@pytest.mark.parametrize("name", ["withdraw", "accept-quote", "reject-quote"])
def test_another_business_cannot_act_on_an_engagement(
    client, setup, make_business, auth_headers, name
):
    engagement = request_gst(client, setup)
    if name != "withdraw":
        action(client, setup["ca_headers"], engagement["id"], "quote", quote_body(engagement))
    other_owner, _ = make_business("Someone Else")

    response = action(client, auth_headers(other_owner), engagement["id"], name)

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "ENGAGEMENT_NOT_FOUND"


# --- Find a CA ranked for the business's own filings ------------------------------------


def test_cas_offering_my_filings_come_first_with_their_prices(
    client, make_business, add_filing, make_ca, make_user, auth_headers, database
):
    owner, business = make_business()
    add_filing(business, FormCode.GSTR_3B, "Aug 2026")
    _, far_ca = make_ca({"tds_26q": "900"}, name="Aaron Far")  # none of my filings
    _, near_ca = make_ca({"gstr_3b": "600"}, name="Zara Near")
    far_ca.city = "Chennai"
    database.session.commit()

    ranked = client.get(f"{BASE}/cas", headers=auth_headers(owner)).get_json()["items"]
    unregistered = auth_headers(make_user(role=UserRole.BUSINESS))
    plain = client.get(f"{BASE}/cas", headers=unregistered).get_json()["items"]

    assert [row["full_name"] for row in ranked] == ["Zara Near", "Aaron Far"]
    assert ranked[0]["my_prices"] == [{"form_code": "gstr_3b", "price": "600.00"}]
    assert (ranked[0]["same_city"], ranked[1]["same_city"]) == (True, False)
    assert ranked[1]["my_prices"] == []
    # Before registering nothing changes: the usual order (experience, name), no ranking data.
    assert [row["full_name"] for row in plain] == ["Aaron Far", "Zara Near"]
    assert all(row["my_prices"] == [] and row["same_city"] is None for row in plain)
    assert all(row["match_score"] is None and row["match_reasons"] == [] for row in plain)


# --- MA8: the matching score and its reasons ---------------------------------------------


def _reasons(row) -> dict:
    """{reason: points} of one CA in the list."""
    result = {}
    for item in row["match_reasons"]:
        result[item["reason"]] = item["points"]
    return result


def _ca_named(rows, name):
    return next(row for row in rows if row["full_name"] == name)


def test_the_match_score_adds_up_its_reasons(client, setup, auth_headers):
    # setup: a Pune business with GSTR-3B and GSTR-1 due; a Pune CA with 5 years, room
    # for 10 clients, prices for both and GSTR-3B as a specialization.
    rows = client.get(f"{BASE}/cas", headers=setup["business_headers"]).get_json()["items"]

    row = rows[0]
    assert _reasons(row) == {
        "Handles 2 of your filings (GSTR-1, GSTR-3B)": 2
        * marketplace_service.POINTS_PER_FORM_OFFERED,
        "Specializes in GSTR-3B": marketplace_service.POINTS_PER_SPECIALIZATION,
        "In your city (Pune)": marketplace_service.POINTS_SAME_CITY,
        "Has room for new clients": marketplace_service.POINTS_HAS_ROOM,
        "5 years of experience": 5 * marketplace_service.POINTS_PER_YEAR_OF_EXPERIENCE,
    }
    assert row["match_score"] == sum(_reasons(row).values())


def test_the_best_match_comes_first_not_the_most_experienced(
    client, make_business, add_filing, make_ca, database, auth_headers
):
    owner, business = make_business()
    add_filing(business, FormCode.GSTR_3B, "Aug 2026")
    _, veteran = make_ca({}, name="Aaron Veteran")  # 30 years, but none of my filings
    veteran.years_experience = 30
    make_ca({"gstr_3b": "600"}, name="Zara Match")
    database.session.commit()

    rows = client.get(f"{BASE}/cas", headers=auth_headers(owner)).get_json()["items"]

    assert [row["full_name"] for row in rows] == ["Zara Match", "Aaron Veteran"]
    # Experience counts at most MAX_EXPERIENCE_YEARS_COUNTED years.
    assert _reasons(rows[1])["30 years of experience"] == (
        marketplace_service.MAX_EXPERIENCE_YEARS_COUNTED
        * marketplace_service.POINTS_PER_YEAR_OF_EXPERIENCE
    )


def test_a_fee_at_or_below_the_typical_fee_earns_points(
    client, make_business, add_filing, make_ca, auth_headers
):
    owner, business = make_business()
    add_filing(business, FormCode.GSTR_3B, "Aug 2026")
    # Three CAs price GSTR-3B, so the typical (median) fee is ₹600.
    make_ca({"gstr_3b": "500"}, name="Asha Low")
    make_ca({"gstr_3b": "600"}, name="Bina Median")
    make_ca({"gstr_3b": "700"}, name="Chitra High")

    rows = client.get(f"{BASE}/cas", headers=auth_headers(owner)).get_json()["items"]

    fair = "Fee at or below the typical fee (GSTR-3B)"
    assert fair in _reasons(_ca_named(rows, "Asha Low"))
    assert fair in _reasons(_ca_named(rows, "Bina Median"))
    assert fair not in _reasons(_ca_named(rows, "Chitra High"))
    assert rows[-1]["full_name"] == "Chitra High"


def test_a_good_rating_and_free_slots_earn_points(
    client, make_business, add_filing, make_ca, database, auth_headers
):
    owner, business = make_business()
    add_filing(business, FormCode.GSTR_3B, "Aug 2026")
    _, rated = make_ca({"gstr_3b": "600"}, name="Rated CA")
    _, busy = make_ca({"gstr_3b": "600"}, name="Busy CA")
    busy.capacity = 3
    # Two finished engagements rated 5 and 4 stars (average 4.5).
    for stars in (5, 4):
        other_owner, other_business = make_business(name=f"Client {stars}")
        done = Engagement(
            business_id=other_business.id,
            ca_profile_id=rated.id,
            status=EngagementStatus.COMPLETED,
        )
        database.session.add(done)
        database.session.flush()
        database.session.add(Rating(engagement_id=done.id, stars=stars))
    # Busy CA: 2 active clients of 3 slots, so less than half is free.
    for number in (1, 2):
        other_owner, other_business = make_business(name=f"Active client {number}")
        database.session.add(
            Engagement(
                business_id=other_business.id,
                ca_profile_id=busy.id,
                status=EngagementStatus.ACTIVE,
            )
        )
    database.session.commit()

    rows = client.get(f"{BASE}/cas", headers=auth_headers(owner)).get_json()["items"]

    rated_reasons = _reasons(_ca_named(rows, "Rated CA"))
    busy_reasons = _reasons(_ca_named(rows, "Busy CA"))
    assert rated_reasons["Rated 4.5 by 2 client(s)"] == marketplace_service.POINTS_GOOD_RATING
    assert "Has room for new clients" in rated_reasons
    assert "Has room for new clients" not in busy_reasons
    assert [row["full_name"] for row in rows] == ["Rated CA", "Busy CA"]


# --- MA12: requests nobody answers within 48 hours expire -----------------------------


def _make_overdue(database, engagement_id):
    """Move a request's answer deadline into the past (instead of waiting 48 hours)."""
    row = database.session.get(Engagement, uuid.UUID(engagement_id))
    row.expires_at = utcnow() - timedelta(minutes=1)
    database.session.commit()


def test_expire_job_expires_only_overdue_requests(client, setup, mailbox, database, make_ca):
    overdue = request_gst(client, setup)
    _make_overdue(database, overdue["id"])
    # A fresh request (another CA, another business filing) must stay requested.
    _, other_ca = make_ca({"gstr_3b": "700"}, name="Other CA")
    mailbox.clear()

    count = marketplace_service.expire_old_requests()

    assert count == 1
    database.session.expire_all()
    assert database.session.get(Engagement, uuid.UUID(overdue["id"])).status == "expired"
    # The business is told, with the service to look for again.
    assert mailbox[0]["To"] == setup["owner"].email
    assert "GSTR-3B filing" in mailbox[0].get_content()
    # The filings are free again: another CA can be requested.
    again = send_request(client, setup, (setup["gst_3b"], setup["catalog"]["gstr_3b"]), ca=other_ca)
    assert again.status_code == 201


def test_expire_job_leaves_quotes_and_answered_requests(client, setup, database):
    quoted = request_gst(client, setup)
    prices = []
    for item in quoted["items"]:
        prices.append({"engagement_item_id": item["id"], "price": "900"})
    action(
        client, setup["ca_headers"], quoted["id"], "quote", {"reason": "Busy.", "prices": prices}
    )
    _make_overdue(database, quoted["id"])

    count = marketplace_service.expire_old_requests()

    assert count == 0
    database.session.expire_all()
    assert database.session.get(Engagement, uuid.UUID(quoted["id"])).status == "quoted"


@pytest.mark.parametrize("name", ["accept", "decline", "quote"])
def test_ca_cannot_answer_after_48_hours(client, setup, database, name):
    engagement = request_gst(client, setup)
    _make_overdue(database, engagement["id"])
    body = None
    if name == "quote":
        body = {
            "reason": "Late.",
            "prices": [{"engagement_item_id": engagement["items"][0]["id"], "price": "1"}],
        }

    response = action(client, setup["ca_headers"], engagement["id"], name, body)

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "REQUEST_EXPIRED"


def test_worker_runs_the_expiry_job_every_15_minutes(app):
    scheduler = build_scheduler(app)

    job = scheduler.get_job("marketplace.expire_requests")

    assert job is not None
    assert job.trigger.interval == timedelta(minutes=15)


# --- MA14: what a CA may see of a business -------------------------------------------


def _add_document(database, owner, filing=None, name="sales.pdf"):
    """A document owned by the business owner, linked to `filing` when given."""
    document = Document(
        owner_id=owner.id,
        uploaded_by_id=owner.id,
        doc_type=DocumentType.SALES_REGISTER,
        original_filename=name,
        storage_key="test-" + str(uuid.uuid4()),
        mime_type="application/pdf",
        size_bytes=10,
        sha256="0" * 64,
    )
    database.session.add(document)
    database.session.flush()
    if filing is not None:
        database.session.add(
            ComplianceItemDocument(
                compliance_item_id=filing.id, document_id=document.id, linked_by_id=owner.id
            )
        )
    database.session.commit()
    return document


def test_access_only_while_the_engagement_is_active(client, setup):
    ca, business = setup["ca"], setup["business"]
    engagement = request_gst(client, setup)
    assert marketplace_service.ca_has_active_access(ca.id, business.id) is False  # requested

    action(client, setup["ca_headers"], engagement["id"], "accept")
    assert marketplace_service.ca_has_active_access(ca.id, business.id) is True

    action(client, setup["ca_headers"], engagement["id"], "complete")
    assert marketplace_service.ca_has_active_access(ca.id, business.id) is False


def test_access_is_per_ca_and_per_business(client, setup, make_ca, make_business):
    engagement = request_gst(client, setup)
    action(client, setup["ca_headers"], engagement["id"], "accept")
    _, other_ca = make_ca({"gstr_3b": "700"}, name="Other CA")
    _, other_business = make_business("Someone Else")

    assert marketplace_service.ca_has_active_access(other_ca.id, setup["business"].id) is False
    assert marketplace_service.ca_has_active_access(setup["ca"].id, other_business.id) is False


def test_each_ca_sees_only_the_filings_they_work_on(client, setup, make_ca, auth_headers):
    business, catalog = setup["business"], setup["catalog"]
    # CA 1 does GSTR-3B, CA 2 does GSTR-1, for the same business.
    first = send_request(client, setup, (setup["gst_3b"], catalog["gstr_3b"])).get_json()
    action(client, setup["ca_headers"], first["id"], "accept")
    second_user, second_ca = make_ca({"gstr_1": "500"}, name="Second CA")
    second = send_request(
        client, setup, (setup["gst_1"], catalog["gstr_1"]), ca=second_ca
    ).get_json()
    action(client, auth_headers(second_user), second["id"], "accept")

    assert marketplace_service.active_engagement_item_ids(setup["ca"].id, business.id) == {
        setup["gst_3b"].id
    }
    assert marketplace_service.active_engagement_item_ids(second_ca.id, business.id) == {
        setup["gst_1"].id
    }


def test_open_items_cover_requests_but_not_ended_ones(client, setup):
    ca, business = setup["ca"], setup["business"]
    engagement = request_gst(client, setup)

    both = {setup["gst_3b"].id, setup["gst_1"].id}
    assert marketplace_service.open_engagement_item_ids(ca.id, business.id) == both
    assert marketplace_service.active_engagement_item_ids(ca.id, business.id) == set()

    action(client, setup["ca_headers"], engagement["id"], "decline")
    assert marketplace_service.open_engagement_item_ids(ca.id, business.id) == set()


def test_documents_only_of_filings_in_active_work(client, setup, database):
    owner, ca = setup["owner"], setup["ca"]
    linked = _add_document(database, owner, setup["gst_3b"], "sales.pdf")
    acknowledgement = _add_document(database, owner, None, "ack.pdf")
    filing = database.session.get(ComplianceItem, setup["gst_1"].id)
    filing.acknowledgement_document_id = acknowledgement.id
    database.session.commit()
    unrelated = _add_document(database, owner, None, "other.pdf")
    engagement = request_gst(client, setup)

    assert marketplace_service.ca_can_access_document(ca.id, linked.id) is False  # not active yet

    action(client, setup["ca_headers"], engagement["id"], "accept")
    assert marketplace_service.ca_can_access_document(ca.id, linked.id) is True
    assert marketplace_service.ca_can_access_document(ca.id, acknowledgement.id) is True
    assert marketplace_service.ca_can_access_document(ca.id, unrelated.id) is False

    action(client, setup["ca_headers"], engagement["id"], "complete")
    assert marketplace_service.ca_can_access_document(ca.id, linked.id) is False


def test_require_ca_access_for_ca_routes(app, client, setup, make_user, auth_headers):
    business = setup["business"]
    engagement = request_gst(client, setup)
    no_profile_ca = make_user(role=UserRole.CA)

    def check(headers):
        with app.test_request_context(headers=headers):
            verify_jwt_in_request()
            require_ca_access(business.id)

    # Only a request so far, and a CA without a profile: 404 BUSINESS_NOT_FOUND.
    for headers in [setup["ca_headers"], auth_headers(no_profile_ca)]:
        with pytest.raises(ApiError) as error:
            check(headers)
        assert error.value.status == 404
        assert error.value.code == "BUSINESS_NOT_FOUND"

    action(client, setup["ca_headers"], engagement["id"], "accept")
    check(setup["ca_headers"])  # active: no error


# --- MA17: ratings ----------------------------------------------------------------------


def _completed(client, setup):
    """A request the CA accepted and completed; returns the engagement JSON."""
    engagement = request_gst(client, setup)
    action(client, setup["ca_headers"], engagement["id"], "accept")
    action(client, setup["ca_headers"], engagement["id"], "complete")
    return engagement


def test_business_rates_completed_work_once(client, setup):
    engagement = _completed(client, setup)
    headers = setup["business_headers"]

    response = action(
        client, headers, engagement["id"], "rating", {"stars": 4, "review": " Quick. "}
    )

    assert response.status_code == 200
    rating = response.get_json()["rating"]
    assert (rating["stars"], rating["review"]) == (4, "Quick.")
    again = action(client, headers, engagement["id"], "rating", {"stars": 5})
    assert again.status_code == 409
    assert again.get_json()["error"]["code"] == "ALREADY_RATED"


def test_only_completed_work_can_be_rated(client, setup):
    engagement = request_gst(client, setup)
    action(client, setup["ca_headers"], engagement["id"], "accept")  # active, not completed

    response = action(client, setup["business_headers"], engagement["id"], "rating", {"stars": 5})

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "INVALID_STATUS"


@pytest.mark.parametrize(
    "body", [{"stars": 0}, {"stars": 6}, {"stars": 3, "review": "x" * 2001}, {}]
)
def test_invalid_ratings_are_rejected(client, setup, body):
    engagement = _completed(client, setup)

    response = action(client, setup["business_headers"], engagement["id"], "rating", body)

    assert response.status_code == 422


def test_only_the_business_of_the_engagement_can_rate(client, setup, make_business, auth_headers):
    engagement = _completed(client, setup)
    other_owner, _ = make_business("Someone Else")

    by_other = action(client, auth_headers(other_owner), engagement["id"], "rating", {"stars": 1})
    by_ca = action(client, setup["ca_headers"], engagement["id"], "rating", {"stars": 5})

    assert by_other.status_code == 404
    assert by_ca.status_code == 403


def test_average_and_reviews_show_on_the_ca_list_and_page(client, setup, add_filing, database):
    ca = setup["ca"]
    headers = setup["business_headers"]
    list_row = client.get(f"{BASE}/cas", headers=headers).get_json()["items"][0]
    assert (list_row["rating_average"], list_row["rating_count"]) == (None, 0)

    first = _completed(client, setup)
    action(client, headers, first["id"], "rating", {"stars": 5, "review": "Great"})
    # A second completed engagement with the same CA, on new filings.
    newer = add_filing(setup["business"], FormCode.GSTR_3B, "Sep 2026", days=40)
    second = send_request(client, setup, (newer, setup["catalog"]["gstr_3b"])).get_json()
    action(client, setup["ca_headers"], second["id"], "accept")
    action(client, setup["ca_headers"], second["id"], "complete")
    action(client, headers, second["id"], "rating", {"stars": 4})

    list_row = client.get(f"{BASE}/cas", headers=headers).get_json()["items"][0]
    page = client.get(f"{BASE}/cas/{ca.id}", headers=headers).get_json()

    assert (list_row["rating_average"], list_row["rating_count"]) == (4.5, 2)
    assert (page["rating_average"], page["rating_count"]) == (4.5, 2)
    assert [review["stars"] for review in page["reviews"]] == [4, 5]  # newest first
    assert page["reviews"][0]["review"] is None
    assert "business_name" not in page["reviews"][0]  # anonymous


# --- MA16: pro-bono queue -----------------------------------------------------------------


def _pledge(database, ca_profile, slots):
    ca_profile.pro_bono_slots_per_month = slots
    database.session.commit()


def _join(client, s, filings, note=""):
    ids = []
    for filing in filings:
        ids.append(str(filing.id))
    body = {"compliance_item_ids": ids, "note": note}
    return client.post(f"{BASE}/pro-bono", json=body, headers=s["business_headers"])


def test_pro_bono_page_for_a_micro_business(client, setup, database):
    give_profile(database, setup["business"], ItrForm.ITR_3)

    page = client.get(f"{BASE}/pro-bono", headers=setup["business_headers"]).get_json()

    assert page["eligible"] is True
    assert page["request"] is None
    assert [row["blocked_reason"] for row in page["filings"]] == [None, None]


def test_only_micro_businesses_may_ask(client, setup, database):
    # No regulatory profile at all, then a small (not micro) one.
    assert (
        client.get(f"{BASE}/pro-bono", headers=setup["business_headers"]).get_json()["eligible"]
        is False
    )
    give_profile(database, setup["business"], ItrForm.ITR_3)
    profile = database.session.query(RegulatoryProfile).one()
    profile.msme_tier = MsmeTier.SMALL
    database.session.commit()

    response = _join(client, setup, [setup["gst_3b"]])

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "NOT_ELIGIBLE_FOR_PRO_BONO"


def test_joining_and_leaving_the_queue(client, setup, database):
    give_profile(database, setup["business"], ItrForm.ITR_3)

    joined = _join(client, setup, [setup["gst_3b"], setup["gst_3b"]], " Small shop ")
    again = _join(client, setup, [setup["gst_1"]])
    page = client.get(f"{BASE}/pro-bono", headers=setup["business_headers"]).get_json()

    assert joined.status_code == 201
    assert joined.get_json()["status"] == "queued"
    assert joined.get_json()["note"] == "Small shop"
    assert len(joined.get_json()["filings"]) == 1  # the same filing once
    assert again.get_json()["error"]["code"] == "PRO_BONO_ALREADY_QUEUED"
    assert page["request"]["id"] == joined.get_json()["id"]

    request_id = joined.get_json()["id"]
    left = client.post(f"{BASE}/pro-bono/{request_id}/cancel", headers=setup["business_headers"])
    twice = client.post(f"{BASE}/pro-bono/{request_id}/cancel", headers=setup["business_headers"])
    assert left.get_json()["status"] == "cancelled"
    assert twice.get_json()["error"]["code"] == "PRO_BONO_NOT_QUEUED"


def test_filings_already_with_a_ca_cannot_join(client, setup, database):
    give_profile(database, setup["business"], ItrForm.ITR_3)
    request_gst(client, setup)  # both filings requested from a paid CA

    response = _join(client, setup, [setup["gst_3b"]])

    assert response.get_json()["error"]["code"] == "FILING_ALREADY_REQUESTED"


def test_ca_takes_a_request_from_the_queue(client, setup, database, mailbox):
    give_profile(database, setup["business"], ItrForm.ITR_3)
    _pledge(database, setup["ca"], 1)
    request_id = _join(client, setup, [setup["gst_3b"], setup["gst_1"]], "Please help").get_json()[
        "id"
    ]
    mailbox.clear()

    queue = client.get(f"{BASE}/pro-bono-queue", headers=setup["ca_headers"]).get_json()
    assert (queue["pledged"], queue["used_this_month"], queue["verified"]) == (1, 0, True)
    assert queue["requests"][0]["business_name"] == "Asha Traders"

    response = client.post(f"{BASE}/pro-bono/{request_id}/accept", headers=setup["ca_headers"])

    engagement = response.get_json()
    assert response.status_code == 200
    assert engagement["status"] == "active"
    assert engagement["is_pro_bono"] is True
    assert {item["agreed_price"] for item in engagement["items"]} == {"0.00"}
    database.session.expire_all()
    assert database.session.get(ComplianceItem, setup["gst_3b"].id).status == "with_ca"
    assert "for free" in mailbox[0].get_content()
    after = client.get(f"{BASE}/pro-bono-queue", headers=setup["ca_headers"]).get_json()
    assert (after["used_this_month"], after["requests"]) == (1, [])


def test_pro_bono_slots_and_verification(client, setup, database, make_ca, auth_headers):
    give_profile(database, setup["business"], ItrForm.ITR_3)
    request_id = _join(client, setup, [setup["gst_3b"]]).get_json()["id"]
    unverified_user, unverified = make_ca({}, status=CaVerificationStatus.PENDING, name="New CA")
    _pledge(database, unverified, 2)

    def accept(headers):
        response = client.post(f"{BASE}/pro-bono/{request_id}/accept", headers=headers)
        return response.get_json()["error"]["code"]

    assert accept(setup["ca_headers"]) == "NO_PRO_BONO_SLOTS"  # pledged 0
    assert accept(auth_headers(unverified_user)) == "CA_NOT_VERIFIED"
    _pledge(database, setup["ca"], 1)
    client.post(f"{BASE}/pro-bono/{request_id}/cancel", headers=setup["business_headers"])
    assert accept(setup["ca_headers"]) == "PRO_BONO_NOT_QUEUED"


def test_a_filing_taken_meanwhile_stops_the_match(client, setup, database):
    give_profile(database, setup["business"], ItrForm.ITR_3)
    _pledge(database, setup["ca"], 1)
    request_id = _join(client, setup, [setup["gst_3b"]]).get_json()["id"]
    request_gst(client, setup)  # the business then asked a paid CA for the same filing

    response = client.post(f"{BASE}/pro-bono/{request_id}/accept", headers=setup["ca_headers"])

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "FILING_ALREADY_REQUESTED"


def test_pro_bono_pages_are_for_their_role(client, setup):
    assert (
        client.get(f"{BASE}/pro-bono-queue", headers=setup["business_headers"]).status_code == 403
    )
    assert client.get(f"{BASE}/pro-bono", headers=setup["ca_headers"]).status_code == 403


# --- AL1: every engagement event also reaches the tray ---------------------------------


def tray(database, user):
    """[(title, body, link)] of the user's tray entries, oldest first."""
    rows = (
        database.session.query(Notification)
        .filter_by(user_id=user.id)
        .order_by(Notification.created_at)
    )
    return [(note.title, note.body, note.link) for note in rows]


def test_a_new_request_reaches_the_cas_tray_and_inbox(client, setup, database, mailbox):
    request_gst(client, setup)

    assert tray(database, setup["ca_user"]) == [
        (
            "New request from Asha Traders",
            "Asha Traders asked you to handle 2 filing(s). Answer within 48 hours.",
            "/ca/engagements",
        )
    ]
    assert mailbox[0]["To"] == setup["ca_user"].email  # the email is unchanged


@pytest.mark.parametrize(
    "name, title, text",
    [
        ("accept", "Your CA accepted your request", "accepted your request"),
        ("decline", "Your CA declined your request", "declined your request"),
        ("quote", "Your CA sent you a quote", "sent a new price. Reason: More invoices"),
    ],
)
def test_the_cas_answer_reaches_the_business_tray(
    client, setup, database, mailbox, name, title, text
):
    engagement = request_gst(client, setup)
    mailbox.clear()
    body = None
    if name == "quote":
        prices = [
            {"engagement_item_id": item["id"], "price": "900"} for item in engagement["items"]
        ]
        body = {"reason": "More invoices", "prices": prices}

    action(client, setup["ca_headers"], engagement["id"], name, body)

    [(tray_title, tray_body, link)] = tray(database, setup["owner"])
    assert tray_title == title
    assert tray_body.startswith(f"Meera Shah {text}")
    assert link == "/business/engagements"
    assert len(mailbox) == 1  # the email is still sent


def test_completion_reaches_the_business_tray_without_email(client, setup, database, mailbox):
    engagement = request_gst(client, setup)
    action(client, setup["ca_headers"], engagement["id"], "accept")
    mailbox.clear()

    action(client, setup["ca_headers"], engagement["id"], "complete")

    assert tray(database, setup["owner"])[-1][0] == "Your CA completed the work"
    assert mailbox == []


def test_an_expired_request_reaches_the_business_tray(client, setup, database):
    engagement = request_gst(client, setup)
    _make_overdue(database, engagement["id"])

    marketplace_service.expire_old_requests()

    [(title, body, _)] = tray(database, setup["owner"])
    assert title == "Your CA request expired"
    assert "Choose another CA for: GSTR-3B filing, GSTR-1 filing." in body


def test_a_pro_bono_match_reaches_the_business_tray(client, setup, database):
    give_profile(database, setup["business"], ItrForm.ITR_3)
    _pledge(database, setup["ca"], 1)
    request_id = _join(client, setup, [setup["gst_3b"]]).get_json()["id"]

    client.post(f"{BASE}/pro-bono/{request_id}/accept", headers=setup["ca_headers"])

    assert tray(database, setup["owner"]) == [
        (
            "A CA will help you for free",
            "Meera Shah took your pro-bono request.",
            "/business/engagements",
        )
    ]


def test_a_refused_action_adds_nothing_to_the_tray(client, setup, database):
    engagement = request_gst(client, setup)
    action(client, setup["ca_headers"], engagement["id"], "decline")

    response = action(client, setup["ca_headers"], engagement["id"], "accept")

    assert response.status_code == 409
    assert [row[0] for row in tray(database, setup["owner"])] == ["Your CA declined your request"]


# --- MA7: capacity (the most active clients a CA takes) ---------------------------------


def _set_capacity(database, ca, capacity):
    ca.capacity = capacity
    database.session.commit()


def _other_client(client, make_business, add_filing, auth_headers, catalog, ca):
    """A second business that requests the CA for one GSTR-3B; returns (headers, response)."""
    owner, business = make_business("Second Shop")
    filing = add_filing(business, FormCode.GSTR_3B, "Aug 2026", days=0)
    headers = auth_headers(owner)
    body = request_body(ca, (filing, catalog["gstr_3b"]))
    return headers, client.post(f"{BASE}/engagements", json=body, headers=headers)


def test_a_full_ca_is_hidden_and_takes_no_new_clients(
    client, setup, database, make_business, add_filing, auth_headers
):
    _set_capacity(database, setup["ca"], 1)
    engagement = request_gst(client, setup)
    action(client, setup["ca_headers"], engagement["id"], "accept")  # 1 active client: full

    listed = client.get(f"{BASE}/cas", headers=setup["business_headers"]).get_json()
    assert str(setup["ca"].id) not in [row["id"] for row in listed["items"]]

    _, response = _other_client(
        client, make_business, add_filing, auth_headers, setup["catalog"], setup["ca"]
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "CA_AT_CAPACITY"
    assert "not taking new clients" in response.get_json()["error"]["message"]


def test_an_existing_client_still_fits(client, setup, database, add_filing):
    _set_capacity(database, setup["ca"], 1)
    first = send_request(client, setup, (setup["gst_3b"], setup["catalog"]["gstr_3b"])).get_json()
    action(client, setup["ca_headers"], first["id"], "accept")

    second = send_request(client, setup, (setup["gst_1"], setup["catalog"]["gstr_1"]))
    assert second.status_code == 201
    accepted = action(client, setup["ca_headers"], second.get_json()["id"], "accept")
    assert accepted.get_json()["status"] == "active"


def test_accepting_or_a_quote_cannot_go_over_capacity(
    client, setup, database, make_business, add_filing, auth_headers
):
    other_headers, pending = _other_client(
        client, make_business, add_filing, auth_headers, setup["catalog"], setup["ca"]
    )
    quoted = pending.get_json()
    action(
        client,
        setup["ca_headers"],
        quoted["id"],
        "quote",
        {
            "reason": "More work",
            "prices": [{"engagement_item_id": quoted["items"][0]["id"], "price": "900"}],
        },
    )
    engagement = request_gst(client, setup)
    _set_capacity(database, setup["ca"], 1)
    action(client, setup["ca_headers"], engagement["id"], "accept")  # now full

    response = action(client, other_headers, quoted["id"], "accept-quote")

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "CA_AT_CAPACITY"


def test_a_pro_bono_match_counts_towards_capacity(
    client, setup, database, make_business, add_filing, auth_headers
):
    give_profile(database, setup["business"], ItrForm.ITR_3)
    _pledge(database, setup["ca"], 2)
    _set_capacity(database, setup["ca"], 1)
    headers, pending = _other_client(
        client, make_business, add_filing, auth_headers, setup["catalog"], setup["ca"]
    )
    action(client, setup["ca_headers"], pending.get_json()["id"], "accept")  # full
    request_id = _join(client, setup, [setup["gst_3b"]]).get_json()["id"]

    response = client.post(f"{BASE}/pro-bono/{request_id}/accept", headers=setup["ca_headers"])

    assert response.get_json()["error"]["code"] == "CA_AT_CAPACITY"
