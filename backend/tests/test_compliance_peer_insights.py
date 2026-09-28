"""GET /api/v1/compliance/items/<id>/peer-insights (CO13): how businesses like this one file
a form (themselves or through a CA) and how often on time. A group is shown only with at
least MIN_PEER_BUSINESSES businesses: the segment (same entity type and MSME tier) first,
then every business, else nothing."""

from datetime import UTC, date, datetime

import pytest

from app.models import Business, ComplianceItem, ObligationTemplate, RegulatoryProfile
from app.models.base import utcnow
from app.models.compliance import ComplianceStatus, FilingPath
from app.models.enums import UserRole
from app.models.onboarding import EntityType
from app.services import compliance_service, onboarding_service

DUE = date(2026, 7, 20)
_counter = iter(range(1, 10_000))


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(compliance_service, "today_in_india", lambda: date(2026, 9, 28))


def make_filer(database, make_user, entity=EntityType.PROPRIETORSHIP, path=None, late=False):
    """A micro business with one GSTR-3B filing (due 20 Jul 2026), filed on `path` (on
    time unless `late`), or not filed when `path` is None. Returns (user, filing)."""
    n = next(_counter)
    user = make_user(role=UserRole.BUSINESS)
    business = Business(
        user_id=user.id,
        legal_name=f"Shop {n}",
        entity_type=entity,
        state="Maharashtra",
        address="Pune",
        description="Shop",
        annual_turnover=2_000_000,
        investment_amount=300_000,
        pan="ABCPE1234F",
        phone="9000000000",
        gst_registered=True,
        gstin="27ABCPE1234F1ZX",
        deducts_tds=False,
        pays_salary_above_limit=False,
    )
    database.session.add(business)
    database.session.flush()
    profile = onboarding_service.compute_profile(business, date(2026, 9, 28))
    database.session.add(
        RegulatoryProfile(business_id=business.id, computed_at=utcnow(), **profile)
    )
    template = database.session.query(ObligationTemplate).filter_by(form_code="gstr_3b").first()
    item = ComplianceItem(
        business_id=business.id,
        template_id=template.id,
        form_code="gstr_3b",
        fy="2026-27",
        period_label="Jun 2026",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        due_date=DUE,
        status=ComplianceStatus.OVERDUE,
    )
    if path is not None:
        item.status = ComplianceStatus.FILED
        item.filing_path = path
        item.filed_at = datetime(2026, 7, 25 if late else 18, 6, 0, tzinfo=UTC)
    database.session.add(item)
    database.session.commit()
    return user, item


def insights(client, auth_headers, user, item):
    response = client.get(
        f"/api/v1/compliance/items/{item.id}/peer-insights", headers=auth_headers(user)
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def test_segment_figures_with_ten_similar_businesses(
    client, database, make_user, auth_headers, legal_rules
):
    # 6 self-filed (1 late), 4 via a CA (all on time); plus one that has not filed.
    for index in range(6):
        make_filer(database, make_user, path=FilingPath.SELF, late=index == 0)
    for _ in range(4):
        make_filer(database, make_user, path=FilingPath.CA)
    user, item = make_filer(database, make_user)

    body = insights(client, auth_headers, user, item)

    assert body["scope"] == "segment"
    assert (body["entity_type"], body["msme_tier"]) == ("proprietorship", "micro")
    assert (body["business_count"], body["filing_count"]) == (10, 10)
    assert body["self"] == {"count": 6, "share_pct": 60, "on_time_pct": 83}
    assert body["ca"] == {"count": 4, "share_pct": 40, "on_time_pct": 100}


def test_overall_figures_when_the_segment_is_too_small(
    client, database, make_user, auth_headers, legal_rules
):
    for _ in range(9):
        make_filer(database, make_user, path=FilingPath.SELF)
    make_filer(database, make_user, entity=EntityType.PARTNERSHIP, path=FilingPath.CA)
    user, item = make_filer(database, make_user, entity=EntityType.PARTNERSHIP)

    body = insights(client, auth_headers, user, item)

    assert body["scope"] == "overall"
    assert body["business_count"] == 10
    assert body["self"]["share_pct"] == 90


def test_nothing_below_ten_businesses(client, database, make_user, auth_headers, legal_rules):
    for _ in range(9):
        make_filer(database, make_user, path=FilingPath.SELF)
    user, item = make_filer(database, make_user)

    body = insights(client, auth_headers, user, item)

    assert body["scope"] == "none"
    assert body["self"] is None and body["ca"] is None
    assert body["min_businesses"] == 10


def test_only_the_owner_sees_a_filings_insights(
    client, database, make_user, auth_headers, legal_rules
):
    _, item = make_filer(database, make_user)
    other, _ = make_filer(database, make_user)

    response = client.get(
        f"/api/v1/compliance/items/{item.id}/peer-insights", headers=auth_headers(other)
    )

    assert response.get_json()["error"]["code"] == "FILING_NOT_FOUND"
    ca = make_user(role=UserRole.CA)
    assert (
        client.get(
            f"/api/v1/compliance/items/{item.id}/peer-insights", headers=auth_headers(ca)
        ).status_code
        == 403
    )


def test_filed_on_time_uses_the_indian_date():
    item = ComplianceItem(due_date=DUE)
    item.filed_at = datetime(2026, 7, 20, 19, 0, tzinfo=UTC)  # 21 Jul, 00:30 in India
    assert compliance_service.filed_on_time(item) is False
    item.filed_at = datetime(2026, 7, 20, 18, 0, tzinfo=UTC)  # 20 Jul, 23:30 in India
    assert compliance_service.filed_on_time(item) is True
