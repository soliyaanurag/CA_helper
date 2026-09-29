"""Financial-year periods and the due-date calculator (compliance_service, CO2).

The rules here are made up for the tests, except the last test, which checks seeded ones.
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


def test_the_seeded_itr_and_gstr4_dates(legal_rules, database):
    """The real seeded rules (checked on 29 Sep 2026): ITR on 31 August without an audit and
    31 October with one; GSTR-4 on 30 June after the financial year."""
    templates = {t.form_code: t for t in database.session.query(ObligationTemplate)}
    year_end = date(2027, 3, 31)

    assert due_date(templates["itr"], year_end) == date(2027, 8, 31)
    assert due_date(templates["itr"], year_end, audit=True) == date(2027, 10, 31)
    assert due_date(templates["gstr_4"], year_end) == date(2027, 6, 30)


def test_the_seeded_itr_date_by_form(legal_rules, database):
    """Individuals and HUFs with business income (ITR-3, ITR-4) without an audit: 31 August;
    ITR-5 (firms, LLPs) without an audit: 31 July (TODO_VERIFY, the earlier of the two dates
    the sources give); any audit, whatever the form: 31 October. GSTR-4: 30 June
    (Notification 12/2024-CT)."""
    itr = database.session.query(ObligationTemplate).filter_by(form_code="itr").one()
    gstr_4 = database.session.query(ObligationTemplate).filter_by(form_code="gstr_4").one()
    year_end = date(2027, 3, 31)

    assert due_date(itr, year_end, itr_form="itr_3") == date(2027, 8, 31)
    assert due_date(itr, year_end, itr_form="itr_4") == date(2027, 8, 31)
    assert due_date(itr, year_end, itr_form="itr_5") == date(2027, 7, 31)
    assert due_date(itr, year_end, audit=True, itr_form="itr_5") == date(2027, 10, 31)
    assert due_date(itr, year_end, audit=True, itr_form="itr_6") == date(2027, 10, 31)
    assert "TODO_VERIFY" in itr.source_reference and "ITR-5" in itr.source_reference
    assert "12/2024-CT" in gstr_4.source_reference
