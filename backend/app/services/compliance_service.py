"""Business logic for compliance: due dates, creating filings, the filings list and the dashboard.

financial_year_start(day) -> date                   1 April of the financial year of `day`
periods_of_year(frequency, fy_start) -> list        the months / quarters / year of one FY
due_date(template, period_end, quarter, audit)      when one filing is due (CO2)
create_filings(business_id, profile, today) -> int  add the missing filings of this FY (CO3)
list_filings(business) -> list[ComplianceItem]      one business's filings, soonest first
get_filings_by_ids(ids, lock) -> dict               filings by id (used by marketplace)
mark_filings_with_ca(ids)                           set filings to "With CA" (used by marketplace)
get_dashboard(user) -> dict                         the business home page (welcome text for now)

How forms and due dates work: each row of `obligation_templates` says which
businesses a form applies to (`applicability`, matched against the regulatory
profile) and when it is due (`due_date_rule`). The rows are data, seeded in
app/seed.py; no legal date is written in this file (CLAUDE.md rule 3).
"""

import calendar
from datetime import date

from sqlalchemy import or_, select

from app.extensions import db
from app.models import ComplianceItem, ObligationTemplate, RegulatoryProfile, User
from app.models.compliance import ComplianceStatus, FilingPath, Frequency


def financial_year_start(day: date) -> date:
    """1 April of the financial year that `day` falls in (a financial year runs April to March)."""
    if day.month >= 4:
        return date(day.year, 4, 1)
    return date(day.year - 1, 4, 1)


def fy_label(fy_start: date) -> str:
    """The financial year's name, e.g. "2026-27" for 1 April 2026 to 31 March 2027."""
    return f"{fy_start.year}-{str(fy_start.year + 1)[2:]}"


def periods_of_year(frequency: Frequency, fy_start: date) -> list[tuple]:
    """The periods of one financial year: 12 months, 4 quarters or the whole year.

    Each period is (label, start, end, quarter); quarter is 1 to 4 for quarterly
    forms and None otherwise.
    """
    fy = fy_label(fy_start)
    if frequency == Frequency.YEARLY:
        return [(f"FY {fy}", fy_start, date(fy_start.year + 1, 3, 31), None)]

    months_per_period = 1 if frequency == Frequency.MONTHLY else 3
    periods = []
    year = fy_start.year
    month = 4  # the financial year starts in April
    for number in range(1, 12 // months_per_period + 1):
        start = date(year, month, 1)
        last_month = month + months_per_period - 1
        end = date(year, last_month, calendar.monthrange(year, last_month)[1])
        if frequency == Frequency.MONTHLY:
            periods.append((start.strftime("%b %Y"), start, end, None))  # "Apr 2026"
        else:
            periods.append((f"Q{number} {fy}", start, end, number))  # "Q1 2026-27"
        # Move to the next period; after December comes January of the next year.
        month = month + months_per_period
        if month > 12:
            month = month - 12
            year = year + 1
    return periods


def _next_date_after(day: date, month: int, day_of_month: int) -> date:
    """The first date with this month and day that comes after `day`."""
    candidate = date(day.year, month, day_of_month)
    if candidate <= day:
        candidate = date(day.year + 1, month, day_of_month)
    return candidate


def due_date(
    template: ObligationTemplate, period_end: date, quarter: int | None = None, audit: bool = False
) -> date:
    """When the filing for the period ending on `period_end` is due, from the template's rule.

    monthly    {"day": 11}                    the 11th of the month after the period
    quarterly  {"quarters": [[7, 13], ...]}   [month, day] for Q1..Q4, after the quarter ends
    yearly     {"month": 7, "day": 31}        that date after the financial year ends;
               "audit_month"/"audit_day"      used instead when the business has a tax audit
    """
    rule = template.due_date_rule
    if template.frequency == Frequency.MONTHLY:
        next_month = period_end.month % 12 + 1  # December (12) -> January (1)
        return _next_date_after(period_end, next_month, rule["day"])
    if template.frequency == Frequency.QUARTERLY:
        month, day = rule["quarters"][quarter - 1]
        return _next_date_after(period_end, month, day)
    if audit and "audit_month" in rule:
        return _next_date_after(period_end, rule["audit_month"], rule["audit_day"])
    return _next_date_after(period_end, rule["month"], rule["day"])


def _applies_to(template: ObligationTemplate, profile: RegulatoryProfile) -> bool:
    """True if every condition of the template matches the profile.

    {"gst_scheme": ["regular_monthly"]} matches a profile whose gst_scheme is
    "regular_monthly"; {} matches every business.
    """
    for field, allowed_values in template.applicability.items():
        if getattr(profile, field) not in allowed_values:
            return False
    return True


def create_filings(business_id, profile: RegulatoryProfile, today: date) -> int:
    """Add the filings this business must make in the current financial year. Does not commit.

    One filing per applicable form and period. Only periods due today or later are
    added (we cannot know whether older ones were filed before the business joined).
    A filing that already exists is skipped, so running this again is safe.
    Returns how many filings were added.
    """
    fy_start = financial_year_start(today)
    fy = fy_label(fy_start)
    templates = db.session.scalars(
        select(ObligationTemplate).where(
            ObligationTemplate.effective_from <= today,
            or_(ObligationTemplate.effective_to.is_(None), ObligationTemplate.effective_to > today),
        )
    ).all()

    added = 0
    for template in templates:
        if not _applies_to(template, profile):
            continue
        for label, start, end, quarter in periods_of_year(template.frequency, fy_start):
            due = due_date(template, end, quarter, profile.audit_applicable)
            if due < today:
                continue
            exists = db.session.scalar(
                select(ComplianceItem.id).where(
                    ComplianceItem.business_id == business_id,
                    ComplianceItem.form_code == template.form_code,
                    ComplianceItem.period_start == start,
                    ComplianceItem.deleted_at.is_(None),
                )
            )
            if exists:
                continue
            db.session.add(
                ComplianceItem(
                    business_id=business_id,
                    template_id=template.id,
                    form_code=template.form_code,
                    fy=fy,
                    period_label=label,
                    period_start=start,
                    period_end=end,
                    due_date=due,
                    status=ComplianceStatus.UPCOMING,
                )
            )
            added = added + 1
    return added


def list_filings(business) -> list[ComplianceItem]:
    """The business's live filings, the soonest due first."""
    return db.session.scalars(
        select(ComplianceItem)
        .where(ComplianceItem.business_id == business.id, ComplianceItem.deleted_at.is_(None))
        .order_by(ComplianceItem.due_date, ComplianceItem.form_code)
    ).all()


def get_dashboard(user: User) -> dict:
    """Data for the business home dashboard.

    For now only a welcome message; the next deadline, due/overdue counts and the
    penalty estimator come later.
    """
    return {"message": f"Welcome, {user.full_name}"}


# --- Used by the marketplace module (engagements) ------------------------------------


def get_filings_by_ids(filing_ids, lock: bool = False) -> dict:
    """{id: ComplianceItem} for the live filings among `filing_ids`. Does not commit.

    lock=True locks the rows until the caller commits (SELECT ... FOR UPDATE), so two
    requests at the same moment cannot both reserve the same filing.
    """
    stmt = select(ComplianceItem).where(
        ComplianceItem.id.in_(filing_ids), ComplianceItem.deleted_at.is_(None)
    )
    if lock:
        stmt = stmt.with_for_update()
    filings = {}
    for filing in db.session.scalars(stmt):
        filings[filing.id] = filing
    return filings


def mark_filings_with_ca(filing_ids) -> None:
    """A CA now handles these filings: status "With CA", path "ca". Does not commit."""
    for filing in get_filings_by_ids(filing_ids).values():
        filing.status = ComplianceStatus.WITH_CA
        filing.filing_path = FilingPath.CA
