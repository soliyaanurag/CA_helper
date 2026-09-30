"""The overdue job (compliance_service.mark_overdue_filings, CO11).

Filings are made the normal way on 27 Sep 2026, then the job runs on later dates.
For this QRMP business, GSTR-1 for Q2 2026-27 is due on 13 Oct 2026 and GSTR-3B for
the same quarter on 22 Oct 2026 (the seeded rules, marked TODO_VERIFY).
"""

from datetime import date

import pytest

from app.models import Business, ComplianceItem, RegulatoryProfile
from app.models.compliance import ComplianceStatus
from app.models.enums import UserRole
from app.models.onboarding import EntityType, GstScheme
from app.services.compliance_service import create_filings, mark_overdue_filings
from worker import build_scheduler


@pytest.fixture()
def business(make_user, legal_rules, database):
    """A QRMP business with this year's filings, created on 27 Sep 2026."""
    owner = make_user(role=UserRole.BUSINESS)
    business = Business(
        user_id=owner.id,
        legal_name="Asha Traders",
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
    profile = RegulatoryProfile(
        gst_scheme=GstScheme.REGULAR_QRMP, audit_applicable=False, files_24q=False, files_26q=False
    )
    create_filings(business.id, profile, date(2026, 9, 27))
    database.session.commit()
    return business


def filing(database, form_code, period_label) -> ComplianceItem:
    return (
        database.session.query(ComplianceItem)
        .filter_by(form_code=form_code, period_label=period_label)
        .one()
    )


def test_a_filing_turns_overdue_the_day_after_its_due_date(business, database):
    assert filing(database, "gstr_1", "Q2 2026-27").status == ComplianceStatus.UPCOMING

    mark_overdue_filings(date(2026, 10, 13))  # the due date itself: not late yet
    assert filing(database, "gstr_1", "Q2 2026-27").status == ComplianceStatus.UPCOMING

    changed = mark_overdue_filings(date(2026, 10, 14))
    assert changed == 1
    assert filing(database, "gstr_1", "Q2 2026-27").status == ComplianceStatus.OVERDUE
    # Due on 22 Oct: still upcoming.
    assert filing(database, "gstr_3b", "Q2 2026-27").status == ComplianceStatus.UPCOMING


def test_running_again_changes_nothing(business, database):
    assert mark_overdue_filings(date(2026, 10, 23)) == 2  # GSTR-1 and GSTR-3B for Q2
    assert mark_overdue_filings(date(2026, 10, 23)) == 0


@pytest.mark.parametrize("status", [ComplianceStatus.DOCS_PENDING, ComplianceStatus.READY])
def test_other_not_started_states_turn_overdue(business, database, status):
    item = filing(database, "gstr_1", "Q2 2026-27")
    item.status = status
    database.session.commit()

    mark_overdue_filings(date(2026, 10, 14))

    assert filing(database, "gstr_1", "Q2 2026-27").status == ComplianceStatus.OVERDUE


@pytest.mark.parametrize(
    "status",
    [ComplianceStatus.WITH_CA, ComplianceStatus.FILED, ComplianceStatus.FILED_VERIFIED],
)
def test_filings_with_a_ca_or_filed_keep_their_status(business, database, status):
    item = filing(database, "gstr_1", "Q2 2026-27")
    item.status = status
    database.session.commit()

    mark_overdue_filings(date(2026, 10, 14))

    assert filing(database, "gstr_1", "Q2 2026-27").status == status


def test_the_worker_runs_it_every_hour(app):
    job = build_scheduler(app).get_job("compliance.mark_overdue")

    assert job is not None
    assert job.trigger.interval.total_seconds() == 3600
