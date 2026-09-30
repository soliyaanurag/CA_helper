"""The database itself enforces the key rules of the data model (docs/DATA_MODEL.md)."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Business,
    CaProfile,
    ComplianceItem,
    Engagement,
    ObligationTemplate,
    Rating,
)
from app.models.enums import FormCode, UserRole
from app.models.marketplace import CaVerificationStatus
from app.models.onboarding import EntityType


def new_business(user, **changes) -> Business:
    fields = {
        "user_id": user.id,
        "legal_name": "Asha Traders",
        "entity_type": EntityType.PROPRIETORSHIP,
        "state": "Maharashtra",
        "address": "12 MG Road, Pune",
        "description": "Retail shop selling stationery",
        "annual_turnover": Decimal("2500000.00"),
        "investment_amount": Decimal("300000.00"),
        "pan": "ABCPE1234F",
        "phone": "9876543210",
        "gst_registered": False,
        "deducts_tds": False,
        "pays_salary_above_limit": False,
    }
    fields.update(changes)
    return Business(**fields)


def new_ca_profile(user) -> CaProfile:
    return CaProfile(
        user_id=user.id,
        membership_no=str(user.id.int)[:6],
        cop_number="COP-1",
        city="Pune",
        languages=["english"],
        specializations=["itr"],
        capacity=10,
        years_experience=5,
        verification_status=CaVerificationStatus.PENDING,
    )


def new_item(business, template, **changes) -> ComplianceItem:
    fields = {
        "business_id": business.id,
        "template_id": template.id,
        "form_code": FormCode.GSTR_3B,
        "fy": "2026-27",
        "period_label": "Apr 2026",
        "period_start": date(2026, 4, 1),
        "period_end": date(2026, 4, 30),
        "due_date": date(2026, 5, 20),
    }
    fields.update(changes)
    return ComplianceItem(**fields)


def add(database, *rows):
    database.session.add_all(rows)
    database.session.commit()


def refused(database, *rows, constraint: str) -> None:
    """Assert the database refuses these rows because of `constraint`, then clean up."""
    database.session.add_all(rows)
    with pytest.raises(IntegrityError, match=constraint):
        database.session.commit()
    database.session.rollback()


@pytest.fixture()
def template(database):
    row = ObligationTemplate(
        form_code=FormCode.GSTR_3B,
        name="GSTR-3B (monthly)",
        frequency="monthly",
        applicability={},
        due_date_rule={},
        source_reference="TODO_VERIFY test data",
        effective_from=date(2026, 4, 1),
    )
    add(database, row)
    return row


def test_a_user_has_at_most_one_business(database, make_user):
    owner = make_user()
    add(database, new_business(owner))

    refused(
        database,
        new_business(owner, legal_name="Second business"),
        constraint="uq_businesses_user_id",
    )


def test_a_user_has_at_most_one_ca_profile(database, make_user):
    ca = make_user(role=UserRole.CA)
    add(database, new_ca_profile(ca))

    refused(database, new_ca_profile(ca), constraint="uq_ca_profiles_user_id")


def test_gst_registered_needs_a_gstin(database, make_user):
    refused(
        database,
        new_business(make_user(), gst_registered=True, gstin=None),
        constraint="ck_businesses_gstin_when_gst_registered",
    )


def test_deducting_tds_needs_a_tan(database, make_user):
    refused(
        database,
        new_business(make_user(), deducts_tds=True, tan=None),
        constraint="ck_businesses_tan_when_deducts_tds",
    )


@pytest.mark.parametrize("entity_type", [EntityType.LLP, EntityType.PRIVATE_LIMITED])
def test_llps_and_companies_need_a_cin_or_llpin(database, make_user, entity_type):
    refused(
        database,
        new_business(make_user(), entity_type=entity_type, cin_llpin=None),
        constraint="ck_businesses_cin_llpin_for_llp_and_company",
    )


@pytest.mark.parametrize("stars", [0, 6])
def test_ratings_are_1_to_5_stars(database, make_user, stars):
    business = new_business(make_user())
    ca_profile = new_ca_profile(make_user(role=UserRole.CA))
    add(database, business, ca_profile)
    engagement = Engagement(business_id=business.id, ca_profile_id=ca_profile.id)
    add(database, engagement)

    refused(
        database,
        Rating(engagement_id=engagement.id, stars=stars),
        constraint="ck_ratings_stars_1_to_5",
    )


def test_one_filing_per_business_form_and_period(database, make_user, template):
    business = new_business(make_user())
    add(database, business)
    add(database, new_item(business, template))

    refused(
        database,
        new_item(business, template),
        constraint="uq_compliance_items_business_id",
    )
