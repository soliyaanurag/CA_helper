"""Admin: the filing numbers on the admin dashboard (AD5)."""

from datetime import UTC, date, datetime

import pytest

from app.models import ComplianceItem
from app.models.compliance import ComplianceStatus
from app.models.enums import UserRole
from app.services import compliance_service
from tests.test_ca_workspace_clients import filing

BASE = "/api/v1/admin"


@pytest.fixture()
def admin(make_user, auth_headers):
    user = make_user(role=UserRole.ADMIN, full_name="Admin One")
    return user, auth_headers(user)


# --- Filing numbers (AD5) ----------------------------------------------------------------


def test_stats_count_filings_by_status_and_the_overdue_rate(
    client, admin, business_with_filings, database, monkeypatch
):
    _, headers = admin
    monkeypatch.setattr(compliance_service, "today_in_india", lambda: date(2026, 9, 28))
    # Q1 GSTR-1 was due in July: filed on time. Q1 GSTR-3B: filed late. The rest: overdue.
    on_time = filing(database, "gstr_1", "Q1 2026-27")
    on_time.status = ComplianceStatus.FILED
    on_time.filed_at = datetime(2026, 7, 1, 5, 0, tzinfo=UTC)
    late = filing(database, "gstr_3b", "Q1 2026-27")
    late.status = ComplianceStatus.FILED
    late.filed_at = datetime(2026, 9, 1, 5, 0, tzinfo=UTC)
    database.session.commit()
    all_filings = database.session.query(ComplianceItem).all()
    due = [item for item in all_filings if item.due_date < date(2026, 9, 28)]

    stats = client.get(f"{BASE}/stats", headers=headers).get_json()

    assert stats["filings_by_status"]["filed"] == 2
    assert sum(stats["filings_by_status"].values()) == len(all_filings)
    assert stats["filings_due_so_far"] == len(due)
    assert stats["filings_late"] == len(due) - 1
    assert stats["overdue_rate"] == round((len(due) - 1) * 100 / len(due), 1)


def test_overdue_rate_is_empty_before_anything_is_due(client, admin):
    stats = client.get(f"{BASE}/stats", headers=admin[1]).get_json()

    assert stats["overdue_rate"] is None
    assert stats["filings_due_so_far"] == 0
