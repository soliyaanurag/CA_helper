"""Financial-year periods and the due-date calculator (compliance_service, CO2).

The rules here are made up for the tests; the real ones are seeded from app/seed.py.
"""

from datetime import date

from app.models import ObligationTemplate
from app.models.compliance import Frequency
from app.services.compliance_service import (
    due_date,
    financial_year_start,
    fy_label,
    periods_of_year,
)

MONTHLY = ObligationTemplate(frequency=Frequency.MONTHLY, due_date_rule={"day": 11})
QUARTERLY = ObligationTemplate(
    frequency=Frequency.QUARTERLY,
    due_date_rule={"quarters": [[7, 31], [10, 31], [1, 31], [5, 31]]},
)
YEARLY = ObligationTemplate(
    frequency=Frequency.YEARLY,
    due_date_rule={"month": 7, "day": 31, "audit_month": 10, "audit_day": 31},
)


def test_financial_year_runs_april_to_march():
    assert financial_year_start(date(2026, 9, 27)) == date(2026, 4, 1)
    assert financial_year_start(date(2026, 4, 1)) == date(2026, 4, 1)
    assert financial_year_start(date(2027, 3, 31)) == date(2026, 4, 1)
    assert fy_label(date(2026, 4, 1)) == "2026-27"


def test_twelve_months_from_april_to_march():
    months = periods_of_year(Frequency.MONTHLY, date(2026, 4, 1))

    assert len(months) == 12
    assert months[0] == ("Apr 2026", date(2026, 4, 1), date(2026, 4, 30), None)
    assert months[9] == ("Jan 2027", date(2027, 1, 1), date(2027, 1, 31), None)
    assert months[10][2] == date(2027, 2, 28)  # February's last day


def test_four_quarters():
    quarters = periods_of_year(Frequency.QUARTERLY, date(2026, 4, 1))

    assert [q[0] for q in quarters] == ["Q1 2026-27", "Q2 2026-27", "Q3 2026-27", "Q4 2026-27"]
    assert quarters[0][1:] == (date(2026, 4, 1), date(2026, 6, 30), 1)
    assert quarters[3][1:] == (date(2027, 1, 1), date(2027, 3, 31), 4)


def test_one_yearly_period():
    assert periods_of_year(Frequency.YEARLY, date(2026, 4, 1)) == [
        ("FY 2026-27", date(2026, 4, 1), date(2027, 3, 31), None)
    ]


def test_monthly_is_due_the_next_month():
    assert due_date(MONTHLY, date(2026, 4, 30)) == date(2026, 5, 11)
    assert due_date(MONTHLY, date(2026, 12, 31)) == date(2027, 1, 11)  # into the next year


def test_quarterly_uses_the_quarters_own_date():
    assert due_date(QUARTERLY, date(2026, 6, 30), quarter=1) == date(2026, 7, 31)
    assert due_date(QUARTERLY, date(2026, 12, 31), quarter=3) == date(2027, 1, 31)
    assert due_date(QUARTERLY, date(2027, 3, 31), quarter=4) == date(2027, 5, 31)


def test_yearly_is_due_after_the_year_and_later_with_an_audit():
    assert due_date(YEARLY, date(2027, 3, 31)) == date(2027, 7, 31)
    assert due_date(YEARLY, date(2027, 3, 31), audit=True) == date(2027, 10, 31)
