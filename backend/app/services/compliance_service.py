"""Business logic for compliance: due dates, creating filings, the filings list and the dashboard.

financial_year_start(day) -> date                   1 April of the financial year of `day`
periods_of_year(frequency, fy_start) -> list        the months / quarters / year of one FY
due_date(template, period_end, quarter, audit)      when one filing is due (CO2)
sync_filings(business_id, profile, today) -> dict  match this FY's filings to the profile (CO3)
create_filings(business_id, profile, today) -> int  the same for a new business (count added)
list_filings(business, filters) -> list             one business's filings, soonest first (CO4)
get_dashboard(user, business) -> dict               home page numbers: next deadline, counts (CO12)
get_form_content(form_code) -> dict                 explanation, instructions, checklist (CO6)
get_filing(business, item_id) -> dict               one filing with its content and checklist (CO5)
choose_path(business, item_id, path) -> dict        "self" or "ca" (CO8)
set_checklist_tick(business, item_id, key, ticked)  tick / untick one checklist entry (CO7, CO10)
mark_filed(business, user, item_id, ack_no, upload) the business filed it itself (CO9)
unmark_filed(business, item_id) -> dict             undo a mistaken "mark as filed"
get_acknowledgement(business, item_id)              the uploaded acknowledgement file
get_filings_by_ids(ids, lock) -> dict               filings by id (used by marketplace)
mark_filings_with_ca(ids)                           set filings to "With CA" (used by marketplace)
mark_overdue_filings(today) -> int                  worker job: late filings -> "overdue" (CO11)
list_unfiled_filings_due_by(day) -> list            not-filed filings due by a date (used by alerts)

How forms and due dates work: each row of `obligation_templates` says which
businesses a form applies to (`applicability`, matched against the regulatory
profile) and when it is due (`due_date_rule`). The rows are data, seeded in
app/seed.py; no legal date is written in this file (CLAUDE.md rule 3).
"""

import calendar
import logging
import re
from datetime import date

import yaml
from sqlalchemy import or_, select

from app.config import REPO_ROOT
from app.errors import ApiError
from app.extensions import db
from app.models import (
    ChecklistTick,
    ComplianceItem,
    ObligationTemplate,
    RegulatoryProfile,
    User,
)
from app.models.base import today_in_india, utcnow
from app.models.compliance import ComplianceStatus, FilingPath, Frequency
from app.models.documents import DocumentType
from app.models.enums import FormCode
from app.services import documents_service

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


def list_filings(
    business, status=None, form_code=None, due_from=None, due_to=None
) -> list[ComplianceItem]:
    """The business's live filings, the soonest due first.

    Optional filters (CO4): one status, one form, and due dates from / to (inclusive).
    """
    stmt = select(ComplianceItem).where(
        ComplianceItem.business_id == business.id, ComplianceItem.deleted_at.is_(None)
    )
    if status is not None:
        stmt = stmt.where(ComplianceItem.status == status)
    if form_code is not None:
        stmt = stmt.where(ComplianceItem.form_code == form_code)
    if due_from is not None:
        stmt = stmt.where(ComplianceItem.due_date >= due_from)
    if due_to is not None:
        stmt = stmt.where(ComplianceItem.due_date <= due_to)
    return db.session.scalars(
        stmt.order_by(ComplianceItem.due_date, ComplianceItem.form_code)
    ).all()


def get_dashboard(user: User, business=None, today: date | None = None) -> dict:
    """The business home page: a welcome, the next deadline and three counts (CO12).

    Counted among filings that are not filed yet: due later this month, overdue (due
    date passed, whatever their status) and with a CA. Before registration only the
    welcome is filled in. The penalty estimate comes with the penalty rules (AL4, AL5).
    """
    if today is None:
        today = today_in_india()
    result = {
        "message": f"Welcome, {user.full_name}",
        "registered": business is not None,
        "next_deadline": None,
        "due_this_month": 0,
        "overdue": 0,
        "with_ca": 0,
    }
    if business is None:
        return result

    for filing in list_filings(business):  # soonest due first
        if filing.status in DONE_STATUSES:
            continue
        if filing.due_date < today:
            result["overdue"] += 1
        else:
            if result["next_deadline"] is None:
                result["next_deadline"] = filing
            same_month = (filing.due_date.year, filing.due_date.month) == (today.year, today.month)
            if same_month:
                result["due_this_month"] += 1
        if filing.status == ComplianceStatus.WITH_CA:
            result["with_ca"] += 1
    return result


# --- Form content (CO6) --------------------------------------------------------------
# Every form has a folder of human-written files (content/README.md):
#   explanation.md, instructions.md  Markdown with a small front matter block (form, status)
#   checklist.yaml                   the documents to have ready: key, label, required, help

CONTENT_DIR = REPO_ROOT / "content" / "forms"
FORM_FOLDERS = {
    FormCode.ITR: "ITR",
    FormCode.GSTR_1: "GSTR-1",
    FormCode.GSTR_3B: "GSTR-3B",
    FormCode.CMP_08: "CMP-08",
    FormCode.GSTR_4: "GSTR-4",
    FormCode.TDS_24Q: "24Q",
    FormCode.TDS_26Q: "26Q",
}


def _read_page(path) -> tuple[str, str]:
    """(status, markdown) of a content page, without its front matter and HTML comments.

    The front matter is the block between the first two "---" lines, e.g.
    "form: GSTR-3B" and "status: DONE". HTML comments are notes for the writers.
    """
    text = path.read_text(encoding="utf-8")
    status = "TODO"
    if text.startswith("---"):
        _, front_matter, text = text.split("---", 2)
        status = (yaml.safe_load(front_matter) or {}).get("status", "TODO")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return status, text.strip()


def _checklist_of(form_code) -> list[dict]:
    """The form's checklist entries: [{key, label, required, help}]."""
    data = yaml.safe_load((CONTENT_DIR / FORM_FOLDERS[form_code] / "checklist.yaml").read_text())
    entries = []
    for item in data.get("items") or []:
        entries.append(
            {
                "key": item["key"],
                "label": item["label"],
                "required": bool(item.get("required", False)),
                "help": item.get("help"),
            }
        )
    return entries


def get_form_content(form_code) -> dict:
    """A form's explanation and self-filing instructions (Markdown) and its checklist.

    `status` is the pages' writing status ("TODO", "DRAFT" or "DONE"), so the page can
    say when a text is not final. 404 FORM_NOT_FOUND for an unknown form code.
    """
    if form_code not in FORM_FOLDERS:
        raise ApiError(404, "FORM_NOT_FOUND", "There is no such form.")
    form_code = FormCode(form_code)
    folder = CONTENT_DIR / FORM_FOLDERS[form_code]
    explanation_status, explanation = _read_page(folder / "explanation.md")
    instructions_status, instructions = _read_page(folder / "instructions.md")
    status = "DONE"
    if "TODO" in (explanation_status, instructions_status):
        status = "TODO"
    elif "DRAFT" in (explanation_status, instructions_status):
        status = "DRAFT"
    return {
        "form_code": form_code,
        "status": status,
        "explanation": explanation,
        "instructions": instructions,
        "checklist": _checklist_of(form_code),
    }


# --- The filing page (CO5, CO7, CO8, CO9, CO10) --------------------------------------

# Filings the business itself can still work on: choose a path, mark filed.
SELF_FILEABLE_STATUSES = (
    ComplianceStatus.UPCOMING,
    ComplianceStatus.DOCS_PENDING,
    ComplianceStatus.READY,
    ComplianceStatus.OVERDUE,
)


def _own_filing(business, item_id) -> ComplianceItem:
    """One live filing of this business. 404 FILING_NOT_FOUND for anyone else's."""
    filing = db.session.get(ComplianceItem, item_id)
    if filing is None or filing.deleted_at is not None or filing.business_id != business.id:
        raise ApiError(404, "FILING_NOT_FOUND", "This filing was not found.")
    return filing


def _ticked_keys(filing: ComplianceItem) -> set:
    return set(
        db.session.scalars(
            select(ChecklistTick.checklist_key).where(ChecklistTick.compliance_item_id == filing.id)
        )
    )


def _refresh_status(filing: ComplianceItem, today: date) -> None:
    """Work out a not-started filing's status again (CO10). Does not commit.

    Past its due date: overdue. Otherwise from the checklist: nothing ticked yet ->
    upcoming; some ticked but a required document missing -> docs pending; every
    required document ticked -> ready. With a CA, filed and verified filings keep
    their status.
    """
    if filing.status not in SELF_FILEABLE_STATUSES:
        return
    if filing.due_date < today:
        filing.status = ComplianceStatus.OVERDUE
        return
    ticked = _ticked_keys(filing)
    required = [entry["key"] for entry in _checklist_of(filing.form_code) if entry["required"]]
    all_required_ticked = all(key in ticked for key in required)
    if not ticked:
        filing.status = ComplianceStatus.UPCOMING
    elif all_required_ticked:
        filing.status = ComplianceStatus.READY
    else:
        filing.status = ComplianceStatus.DOCS_PENDING


def get_filing(business, item_id) -> dict:
    """One filing with everything its page shows: dates, status, path, the form's
    explanation and instructions, the checklist with ticks, and the acknowledgement."""
    filing = _own_filing(business, item_id)
    content = get_form_content(filing.form_code)
    ticked = _ticked_keys(filing)
    checklist = []
    for entry in content["checklist"]:
        checklist.append({**entry, "ticked": entry["key"] in ticked})
    acknowledgement = None
    if filing.acknowledgement_document_id is not None:
        document, _ = documents_service.read_document(filing.acknowledgement_document_id)
        acknowledgement = {
            "filename": document.original_filename,
            "uploaded_at": document.created_at,
        }
    return {
        "filing": filing,
        "form_name": db.session.get(ObligationTemplate, filing.template_id).name,
        "content_status": content["status"],
        "explanation": content["explanation"],
        "instructions": content["instructions"],
        "checklist": checklist,
        "acknowledgement": acknowledgement,
    }


def choose_path(business, item_id, path: FilingPath) -> dict:
    """The business decides to file it itself ("self") or with a CA ("ca") (CO8).

    409 FILING_LOCKED once a CA has it or it is filed.
    """
    filing = _own_filing(business, item_id)
    if filing.status not in SELF_FILEABLE_STATUSES:
        raise ApiError(409, "FILING_LOCKED", "This filing is already with a CA or filed.")
    filing.filing_path = path
    db.session.commit()
    return get_filing(business, item_id)


def set_checklist_tick(business, item_id, key: str, ticked: bool) -> dict:
    """Tick (or untick) one checklist entry, then update the filing's status (CO7, CO10).

    A tick is a row in checklist_ticks; unticking deletes it (CLAUDE.md rule 6).
    422 UNKNOWN_CHECKLIST_KEY for a key that is not in the form's checklist.
    """
    filing = _own_filing(business, item_id)
    keys = [entry["key"] for entry in _checklist_of(filing.form_code)]
    if key not in keys:
        raise ApiError(422, "UNKNOWN_CHECKLIST_KEY", "This checklist entry does not exist.")
    existing = db.session.scalar(
        select(ChecklistTick).where(
            ChecklistTick.compliance_item_id == filing.id, ChecklistTick.checklist_key == key
        )
    )
    if ticked and existing is None:
        db.session.add(ChecklistTick(compliance_item_id=filing.id, checklist_key=key))
    if not ticked and existing is not None:
        db.session.delete(existing)
    db.session.flush()  # so _refresh_status sees the change
    _refresh_status(filing, today_in_india())
    db.session.commit()
    return get_filing(business, item_id)


def mark_filed(business, user: User, item_id, acknowledgement_no=None, upload=None) -> dict:
    """The business filed it itself on the government portal (CO9).

    Optional: the acknowledgement (ARN) number and the acknowledgement file, which is
    stored encrypted. 409 FILING_WITH_CA (the CA marks it), 409 ALREADY_FILED.
    Storage errors for the file (FILE_TYPE_NOT_ALLOWED, FILE_TOO_LARGE) pass through.
    """
    filing = _own_filing(business, item_id)
    if filing.status == ComplianceStatus.WITH_CA:
        raise ApiError(409, "FILING_WITH_CA", "Your CA is handling this filing.")
    if filing.status not in SELF_FILEABLE_STATUSES:
        raise ApiError(409, "ALREADY_FILED", "This filing is already marked as filed.")
    if upload is not None:
        document = documents_service.add_document(
            user.id, user.id, upload, DocumentType.ACKNOWLEDGEMENT
        )
        document.fy = filing.fy
        document.period_label = filing.period_label
        db.session.flush()  # gives document.id
        filing.acknowledgement_document_id = document.id
    filing.status = ComplianceStatus.FILED
    filing.filing_path = FilingPath.SELF
    filing.filed_at = utcnow()
    filing.acknowledgement_no = acknowledgement_no or None
    db.session.commit()
    log.info("Filing %s marked filed by its business", filing.id)
    return get_filing(business, item_id)


def unmark_filed(business, item_id) -> dict:
    """Undo "mark as filed" (a mistake): the status is worked out again and the
    acknowledgement is removed. Only for filings the business marked itself;
    409 NOT_SELF_FILED otherwise.
    """
    filing = _own_filing(business, item_id)
    if filing.status != ComplianceStatus.FILED or filing.filing_path != FilingPath.SELF:
        raise ApiError(409, "NOT_SELF_FILED", "Only a filing you marked as filed can be undone.")
    if filing.acknowledgement_document_id is not None:
        documents_service.remove_document(filing.acknowledgement_document_id)
    filing.acknowledgement_document_id = None
    filing.acknowledgement_no = None
    filing.filed_at = None
    filing.status = ComplianceStatus.UPCOMING
    _refresh_status(filing, today_in_india())
    db.session.commit()
    return get_filing(business, item_id)


def get_acknowledgement(business, item_id):
    """(document, bytes) of the filing's acknowledgement. 404 ACKNOWLEDGEMENT_MISSING."""
    filing = _own_filing(business, item_id)
    if filing.acknowledgement_document_id is None:
        raise ApiError(404, "ACKNOWLEDGEMENT_MISSING", "No acknowledgement was uploaded.")
    return documents_service.read_document(filing.acknowledgement_document_id)


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


# --- Used by the alerts module (reminders) --------------------------------------------


def list_unfiled_filings_due_by(day: date) -> list[ComplianceItem]:
    """Every business's live filings that are not filed yet and are due on or before `day`,
    soonest due first. The reminder job picks from these."""
    stmt = (
        select(ComplianceItem)
        .where(
            ComplianceItem.due_date <= day,
            ComplianceItem.status.not_in(DONE_STATUSES),
            ComplianceItem.deleted_at.is_(None),
        )
        .order_by(ComplianceItem.due_date)
    )
    return list(db.session.scalars(stmt))


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
