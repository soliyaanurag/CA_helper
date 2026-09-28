"""Business logic for compliance: due dates, creating filings, the filings list and the dashboard.

financial_year_start(day) -> date                   1 April of the financial year of `day`
periods_of_year(frequency, fy_start) -> list        the months / quarters / year of one FY
due_date(template, period_end, quarter, audit)      when one filing is due (CO2)
sync_filings(business_id, profile, today) -> dict  match this FY's filings to the profile (CO3)
create_filings(business_id, profile, today) -> int  the same for a new business (count added)
list_filings(business) -> list[ComplianceItem]      one business's filings, soonest first
get_filings_by_ids(ids, lock) -> dict               filings by id (used by marketplace)
mark_filings_with_ca(ids)                           set filings to "With CA" (used by marketplace)
mark_overdue_filings(today) -> int                  worker job: late filings -> "overdue" (CO11)
get_dashboard(user) -> dict                         the business home page (welcome text for now)

How forms and due dates work: each row of `obligation_templates` says which
businesses a form applies to (`applicability`, matched against the regulatory
profile) and when it is due (`due_date_rule`). The rows are data, seeded in
app/seed.py; no legal date is written in this file (CLAUDE.md rule 3).
"""

import calendar
import logging
from datetime import date

from sqlalchemy import or_, select

from app.extensions import db
from app.models import ComplianceItem, ObligationTemplate, RegulatoryProfile, User
from app.models.base import today_in_india, utcnow
from app.models.compliance import ComplianceStatus, FilingPath, Frequency

log = logging.getLogger(__name__)


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


# Filings in these states are done; a profile change never removes them.
DONE_STATUSES = (ComplianceStatus.FILED, ComplianceStatus.FILED_VERIFIED)


def _status_for(due: date, today: date) -> ComplianceStatus:
    """A filing that is not started yet: overdue once its due date has passed."""
    return ComplianceStatus.OVERDUE if due < today else ComplianceStatus.UPCOMING


def sync_filings(business_id, profile: RegulatoryProfile, today: date, keep_ids=()) -> dict:
    """Make the business's filings of the current financial year match its profile.
    Does not commit.

    - Every applicable form and period gets a filing, from 1 April: periods whose due
      date has passed start as "overdue" (the business may have filed them before it
      joined; it can mark them filed).
    - A soft-deleted filing that applies again is reactivated, not inserted again.
    - A filing that no longer applies is soft-deleted, unless it is filed, with a CA
      (status "with_ca") or in `keep_ids` (filings in an open engagement).
    - A not-started filing whose period or due date changed gets the new one: the audit
      answer moves the ITR date; switching between monthly and quarterly returns turns
      "Q1" into "Apr" (both start on 1 April, and only one live filing per form and start
      date may exist).

    Returns {"added", "restored", "removed", "moved", "kept_with_ca"} counts.
    """
    fy_start = financial_year_start(today)
    fy = fy_label(fy_start)
    audit = bool(profile.audit_applicable or profile.other_audit_applicable)
    templates = db.session.scalars(
        select(ObligationTemplate).where(
            ObligationTemplate.effective_from <= today,
            or_(ObligationTemplate.effective_to.is_(None), ObligationTemplate.effective_to > today),
        )
    ).all()

    # {(form_code, period_start): (template, label, start, end, due date)} for this FY.
    wanted = {}
    for template in templates:
        if _applies_to(template, profile):
            for label, start, end, quarter in periods_of_year(template.frequency, fy_start):
                due = due_date(template, end, quarter, audit)
                wanted[(template.form_code, start)] = (template, label, start, end, due)

    this_year = db.session.scalars(
        select(ComplianceItem)
        .where(ComplianceItem.business_id == business_id, ComplianceItem.fy == fy)
        .order_by(ComplianceItem.created_at)
    ).all()
    live = {}
    deleted = {}
    for item in this_year:
        key = (item.form_code, item.period_start)
        if item.deleted_at is None:
            live[key] = item
        else:
            deleted[key] = item  # the newest one wins

    def reshape(item, template, label, end, due):
        """Give a not-started filing the wanted template, period and due date."""
        item.template_id = template.id
        item.period_label = label
        item.period_end = end
        item.due_date = due
        item.status = _status_for(due, today)

    counts = {"added": 0, "restored": 0, "removed": 0, "moved": 0, "kept_with_ca": 0}
    for key, (template, label, start, end, due) in wanted.items():
        item = live.get(key)
        if item is not None:
            not_started = item.status in (ComplianceStatus.UPCOMING, ComplianceStatus.OVERDUE)
            if not_started and (item.period_end, item.due_date) != (end, due):
                reshape(item, template, label, end, due)
                counts["moved"] += 1
        elif key in deleted:
            item = deleted[key]
            item.is_active = True
            item.deleted_at = None
            if item.status in DONE_STATUSES:
                item.template_id = template.id
            else:
                reshape(item, template, label, end, due)
            counts["restored"] += 1
        else:
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
                    status=_status_for(due, today),
                )
            )
            counts["added"] += 1

    for key, item in live.items():
        if key in wanted or item.status in DONE_STATUSES:
            continue
        if item.status == ComplianceStatus.WITH_CA or item.id in keep_ids:
            counts["kept_with_ca"] += 1
            continue
        item.is_active = False
        item.deleted_at = utcnow()
        counts["removed"] += 1
    return counts


def create_filings(business_id, profile: RegulatoryProfile, today: date) -> int:
    """Add the filings of a newly registered business (sync_filings). Does not commit.

    Returns how many filings were added; running it again adds nothing.
    """
    return sync_filings(business_id, profile, today)["added"]


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


# --- Worker job (CO11) ---------------------------------------------------------------

# The business still has to act on filings in these states, so they turn "overdue" once
# the due date has passed. A filing "With CA" keeps that status: the CA is handling it,
# and the pages already show how late it is from its due date. Filed ones are done.
NOT_STARTED_STATUSES = (
    ComplianceStatus.UPCOMING,
    ComplianceStatus.DOCS_PENDING,
    ComplianceStatus.READY,
)


def mark_overdue_filings(today: date | None = None) -> int:
    """Set every live filing whose due date has passed, and which is not started yet,
    to "overdue". Returns how many changed. The worker runs this every hour.

    A filing due today is not overdue yet. Running it again changes nothing.
    """
    if today is None:
        today = today_in_india()
    late = db.session.scalars(
        select(ComplianceItem).where(
            ComplianceItem.status.in_(NOT_STARTED_STATUSES),
            ComplianceItem.due_date < today,
            ComplianceItem.deleted_at.is_(None),
        )
    ).all()
    for filing in late:
        filing.status = ComplianceStatus.OVERDUE
    db.session.commit()
    if len(late) > 0:
        log.info("Marked %d filing(s) overdue", len(late))
    return len(late)
