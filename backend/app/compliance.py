"""Filings: which forms a business must file and when, the calendar, the filing page
(checklist, path, mark filed), the dashboard numbers, peer insights and the overdue job.

Each row of `obligation_templates` says which businesses a form applies to
(`applicability`, matched against the regulatory profile) and when it is due
(`due_date_rule`). The rows are data, seeded in app/seed.py; no legal date is written
in this file.
"""

import calendar
import io
import logging
import re
from datetime import date
from zoneinfo import ZoneInfo

import yaml
from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import delete, or_, select

from app import documents, onboarding
from app.models import (
    ChecklistTick,
    ComplianceItem,
    ComplianceItemDocument,
    ComplianceStatus,
    DocumentRequest,
    DocumentType,
    EngagementItem,
    FilingPath,
    FormCode,
    Frequency,
    ObligationTemplate,
    RegulatoryProfile,
    ReminderLog,
    User,
    UserRole,
    db,
    today_in_india,
    utcnow,
)
from app.utils import (
    MISSING,
    REPO_ROOT,
    ApiError,
    current_business,
    current_business_or_none,
    current_user,
    iso,
    json_body,
    login_required,
    roles_required,
    validation_error,
)

log = logging.getLogger(__name__)

bp = Blueprint("compliance", __name__)

# Filings in these states are done; a profile change never removes them.
DONE_STATUSES = (ComplianceStatus.FILED, ComplianceStatus.FILED_VERIFIED)

# A group's peer figures are shown only when at least this many businesses have filed the
# form (fewer would say little and could point at one business). A product rule.
MIN_PEER_BUSINESSES = 10


# --- JSON shapes -------------------------------------------------------------------------


def filing_to_dict(filing: ComplianceItem) -> dict:
    """One filing, e.g. GSTR-3B for Apr 2026, due 2026-05-20."""
    return {
        "id": str(filing.id),
        "form_code": filing.form_code,
        "fy": filing.fy,
        "period_label": filing.period_label,
        "period_start": iso(filing.period_start),
        "period_end": iso(filing.period_end),
        "due_date": iso(filing.due_date),
        "status": filing.status,
        "filing_path": filing.filing_path,
    }


def filing_detail_to_dict(filing: ComplianceItem) -> dict:
    """A filing with when it was filed and its acknowledgement (ARN) number."""
    result = filing_to_dict(filing)
    result["filed_at"] = iso(filing.filed_at)
    result["acknowledgement_no"] = filing.acknowledgement_no
    return result


# --- Periods and due dates ---------------------------------------------------------------


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
    template: ObligationTemplate,
    period_end: date,
    quarter: int | None = None,
    audit: bool = False,
    itr_form: str | None = None,
) -> date:
    """When the filing for the period ending on `period_end` is due, from the template's rule.

    monthly    {"day": 11}                    the 11th of the month after the period
    quarterly  {"quarters": [[7, 13], ...]}   [month, day] for Q1..Q4, after the quarter ends
    yearly     {"month": 7, "day": 31}        that date after the financial year ends;
               "audit_month"/"audit_day"      used instead when the business has an audit;
               "by_itr_form": {"itr_5": [7, 31]}   used instead, without an audit, for a
                                              business whose profile has that ITR form
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
    if itr_form in rule.get("by_itr_form", {}):
        month, day = rule["by_itr_form"][itr_form]
        return _next_date_after(period_end, month, day)
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


def _status_for(due: date, today: date) -> ComplianceStatus:
    """A filing that is not started yet: overdue once its due date has passed."""
    return ComplianceStatus.OVERDUE if due < today else ComplianceStatus.UPCOMING


def sync_filings(business_id, profile: RegulatoryProfile, today: date, keep_ids=()) -> dict:
    """Make the business's filings of the current financial year match its profile.
    Returns {"added", "removed", "kept_with_ca"} counts.

    - Every applicable form and period gets a filing, from 1 April: periods whose due
      date has passed start as "overdue" (the business may have filed them before it
      joined; it can mark them filed).
    - A filing that no longer applies is deleted, unless it is filed, with a CA
      (status "with_ca") or in `keep_ids` (filings in an open engagement).
    - A not-started filing gets the current period and due date: the audit answer moves
      the ITR date; switching between monthly and quarterly returns turns "Q1" into "Apr"
      (both start on 1 April, and there is one filing per form and start date).
    """
    fy_start = financial_year_start(today)
    fy = fy_label(fy_start)
    audit = bool(profile.audit_applicable or profile.other_audit_applicable)
    itr_form = profile.itr_form
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
                due = due_date(template, end, quarter, audit, itr_form)
                wanted[(template.form_code, start)] = (template, label, start, end, due)

    this_year = db.session.scalars(
        select(ComplianceItem)
        .where(ComplianceItem.business_id == business_id, ComplianceItem.fy == fy)
        .order_by(ComplianceItem.created_at)
    ).all()
    existing = {}
    for item in this_year:
        existing[(item.form_code, item.period_start)] = item

    counts = {"added": 0, "removed": 0, "kept_with_ca": 0}
    for key, (template, label, start, end, due) in wanted.items():
        item = existing.get(key)
        if item is None:
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
            continue
        item.template_id = template.id  # the rule row in force now
        not_started = item.status in (ComplianceStatus.UPCOMING, ComplianceStatus.OVERDUE)
        if not_started and (item.period_end, item.due_date) != (end, due):
            item.period_label = label
            item.period_end = end
            item.due_date = due
            item.status = _status_for(due, today)

    for key, item in existing.items():
        if key in wanted or item.status in DONE_STATUSES:
            continue
        if item.status == ComplianceStatus.WITH_CA or item.id in keep_ids:
            counts["kept_with_ca"] += 1
            continue
        _delete_filing(item)
        counts["removed"] += 1
    return counts


def _delete_filing(filing) -> None:
    """Delete a filing and the rows that point to it (its files stay in the vault)."""
    for model in (ChecklistTick, ComplianceItemDocument, ReminderLog, DocumentRequest, EngagementItem):
        db.session.execute(delete(model).where(model.compliance_item_id == filing.id))
    db.session.delete(filing)


def create_filings(business_id, profile: RegulatoryProfile, today: date) -> int:
    """Add the filings of a newly registered business (sync_filings).

    Returns how many filings were added; running it again adds nothing.
    """
    return sync_filings(business_id, profile, today)["added"]


def list_filings(
    business, status=None, form_code=None, due_from=None, due_to=None
) -> list[ComplianceItem]:
    """The business's live filings, the soonest due first.

    Optional filters: one status, one form, and due dates from / to (inclusive).
    """
    stmt = select(ComplianceItem).where(
        ComplianceItem.business_id == business.id
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
    """The business home page: a welcome, the next deadline and three counts.

    Counted among filings that are not filed yet: due later this month, overdue (due
    date passed, whatever their status) and with a CA. Before registration only the
    welcome is filled in. The penalty estimate comes with the penalty rules.
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


# --- Form content ------------------------------------------------------------------------
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


# --- The filing page ---------------------------------------------------------------------

# Filings the business itself can still work on: choose a path, mark filed.
SELF_FILEABLE_STATUSES = (
    ComplianceStatus.UPCOMING,
    ComplianceStatus.DOCS_PENDING,
    ComplianceStatus.READY,
    ComplianceStatus.OVERDUE,
)


def _ticked_keys(filing: ComplianceItem) -> set:
    return set(
        db.session.scalars(
            select(ChecklistTick.checklist_key).where(ChecklistTick.compliance_item_id == filing.id)
        )
    )


def _refresh_status(filing: ComplianceItem, today: date) -> None:
    """Work out a not-started filing's status again.

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


def _template_name(filing: ComplianceItem) -> str:
    """The filing's form as its page names it, e.g. "GSTR-3B (quarterly, QRMP)"; a renamed
    form under its new name (RENAMED_FORMS)."""
    renamed = RENAMED_FORMS.get(filing.form_code)
    if renamed is not None and filing.fy >= renamed[0]:
        return renamed[2]
    return db.session.get(ObligationTemplate, filing.template_id).name


def filing_page(filing: ComplianceItem) -> dict:
    """Everything the filing page shows: dates, status, path, the form's explanation and
    instructions, the checklist with ticks, and the acknowledgement."""
    content = get_form_content(filing.form_code)
    acknowledgement = None
    if filing.acknowledgement_document_id is not None:
        # Only the stored metadata: the file itself is not opened for the page.
        document = documents.get_document(filing.acknowledgement_document_id)
        acknowledgement = {
            "filename": document.original_filename,
            "uploaded_at": iso(document.created_at),
            # Why it is (not) verified, from the fields OCR read when it was uploaded.
            "verification": documents.verify_acknowledgement(document, filing),
        }
    return {
        "filing": filing_detail_to_dict(filing),
        "form_name": _template_name(filing),
        "content_status": content["status"],
        "explanation": content["explanation"],
        "instructions": content["instructions"],
        "checklist": checklist_with_ticks(filing),
        "acknowledgement": acknowledgement,
    }


def _set_tick(filing: ComplianceItem, key: str, ticked: bool) -> None:
    """Add or remove one tick, then work out the status again.

    422 UNKNOWN_CHECKLIST_KEY for a key that is not in the form's checklist.
    """
    if key not in checklist_keys(filing.form_code):
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


def _record_filed(filing, owner_id, uploader: User, path, acknowledgement_no, upload) -> None:
    """Status "filed" with the optional ARN and acknowledgement file (owned by the business
    owner, uploaded by `uploader`).

    With a file, the acknowledgement is read locally (documents, OCR) and, when it
    shows this form, period, a number and a filing date, the filing becomes
    "filed_verified". An ARN found in the file fills an empty ARN.
    """
    document = None
    if upload is not None:  # stored first: a refused file changes nothing
        document = documents.add_document(
            owner_id, uploader.id, upload, DocumentType.ACKNOWLEDGEMENT
        )
        document.fy = filing.fy
        document.period_label = filing.period_label
        filing.acknowledgement_document_id = document.id
    filing.status = ComplianceStatus.FILED
    filing.filing_path = path
    filing.filed_at = utcnow()
    filing.acknowledgement_no = acknowledgement_no or None
    if document is None:
        return
    result = documents.verify_acknowledgement(document, filing)
    if result["verified"]:
        filing.status = ComplianceStatus.FILED_VERIFIED
        filing.verified_at = utcnow()
        filing.acknowledgement_no = filing.acknowledgement_no or result["acknowledgement_no"]


# --- For other modules -------------------------------------------------------------------


def checklist_with_ticks(filing: ComplianceItem) -> list[dict]:
    """The form's checklist entries, each with `ticked`: [{key, label, required, help, ticked}]."""
    ticked = _ticked_keys(filing)
    entries = []
    for entry in _checklist_of(filing.form_code):
        entries.append({**entry, "ticked": entry["key"] in ticked})
    return entries


def checklist_progress(filing: ComplianceItem) -> dict:
    """How ready a filing's documents are: {required_total, required_ready, missing (the
    labels of the required entries not ticked yet)}."""
    required = [entry for entry in checklist_with_ticks(filing) if entry["required"]]
    missing = [entry["label"] for entry in required if not entry["ticked"]]
    return {
        "required_total": len(required),
        "required_ready": len(required) - len(missing),
        "missing": missing,
    }


def mark_filed_by_ca(business, ca_user: User, item_id, acknowledgement_no=None, upload=None):
    """The CA of an active engagement filed it: like mark_filed, with the path "ca".
    The acknowledgement belongs to the business owner; the CA is its uploader. Does not
    commit; the caller checks the CA's access first.

    409 ALREADY_FILED; 409 FILING_NOT_WITH_CA unless the filing is "With CA".
    """
    filing = own_filing(business, item_id)
    if filing.status in DONE_STATUSES:
        raise ApiError(409, "ALREADY_FILED", "This filing is already marked as filed.")
    if filing.status != ComplianceStatus.WITH_CA:
        raise ApiError(409, "FILING_NOT_WITH_CA", "This filing is not with you.")
    _record_filed(filing, business.user_id, ca_user, FilingPath.CA, acknowledgement_no, upload)
    log.info("Filing %s marked filed by its CA", filing.id)
    return filing


# --- Used by the documents module ------------------------------------------------------


def checklist_keys(form_code) -> list[str]:
    """The keys of a form's checklist entries, in checklist order."""
    return [entry["key"] for entry in _checklist_of(form_code)]


def tick_checklist_entry(filing: ComplianceItem, key: str) -> None:
    """Tick one checklist entry (a document was linked to it) and update the status.
    422 UNKNOWN_CHECKLIST_KEY for a key not in the form's checklist."""
    _set_tick(filing, key, True)


def filings_by_acknowledgement(document_ids) -> dict:
    """{document id: ComplianceItem} for the live filings whose acknowledgement is one of
    these documents."""
    if len(document_ids) == 0:
        return {}
    stmt = select(ComplianceItem).where(
        ComplianceItem.acknowledgement_document_id.in_(document_ids),
    )
    filings = {}
    for filing in db.session.scalars(stmt):
        filings[filing.acknowledgement_document_id] = filing
    return filings


# --- Used by the marketplace module ----------------------------------------------------


def get_filings_by_ids(filing_ids) -> dict:
    """{id: ComplianceItem} for the live filings among `filing_ids`."""
    stmt = select(ComplianceItem).where(
        ComplianceItem.id.in_(filing_ids)
    )
    filings = {}
    for filing in db.session.scalars(stmt):
        filings[filing.id] = filing
    return filings


def mark_filings_with_ca(filing_ids) -> None:
    """A CA now handles these filings: status "With CA", path "ca"."""
    for filing in get_filings_by_ids(filing_ids).values():
        filing.status = ComplianceStatus.WITH_CA
        filing.filing_path = FilingPath.CA


# --- Used by the alerts module ---------------------------------------------------------


def list_unfiled_filings_due_by(day: date) -> list[ComplianceItem]:
    """Every business's live filings that are not filed yet and are due on or before `day`,
    soonest due first. The reminder job picks from these."""
    stmt = (
        select(ComplianceItem)
        .where(
            ComplianceItem.due_date <= day,
            ComplianceItem.status.not_in(DONE_STATUSES),
        )
        .order_by(ComplianceItem.due_date)
    )
    return list(db.session.scalars(stmt))


def business_ids_with_open_filings(form_codes) -> set:
    """The businesses that still have a live, not-filed filing of one of these forms
    (used by the regulatory module to find who a rule change affects)."""
    stmt = select(ComplianceItem.business_id).where(
        ComplianceItem.form_code.in_(list(form_codes)),
        ComplianceItem.status.not_in(DONE_STATUSES),
    )
    return set(db.session.scalars(stmt))


# --- The overdue job (run by the worker) -------------------------------------------------

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
        )
    ).all()
    for filing in late:
        filing.status = ComplianceStatus.OVERDUE
    db.session.commit()
    if len(late) > 0:
        log.info("Marked %d filing(s) overdue", len(late))
    return len(late)


# --- Forms renamed by law (display names only) ------------------------------------------

# From the first financial year given, a form is shown under its new name; its code, content
# folder and rules stay. The Income-tax Act, 2025 and the Income-tax Rules, 2026 renamed the
# quarterly TDS statements from tax year 2026-27: 24Q is Form 138 and 26Q is Form 140
# (incometax.gov.in, Form 138 / Form 140 user manuals). frontend/src/lib/labels.js
# (RENAMED_FORMS) has the same list.
RENAMED_FORMS = {
    FormCode.TDS_24Q: (
        "2026-27",
        "Form 138 (earlier 24Q)",
        "TDS return, salary (Form 138, earlier 24Q)",
    ),
    FormCode.TDS_26Q: (
        "2026-27",
        "Form 140 (earlier 26Q)",
        "TDS return, other payments (Form 140, earlier 26Q)",
    ),
}


def form_name(form_code, fy: str) -> str:
    """A form's short name for a filing of financial year `fy` ("2026-27"), e.g. "GSTR-3B",
    or "Form 138 (earlier 24Q)" for a 24Q from tax year 2026-27 (the new name)."""
    renamed = RENAMED_FORMS.get(form_code)
    if renamed is not None and fy >= renamed[0]:
        return renamed[1]
    return FORM_FOLDERS[form_code]


def filing_name(filing) -> str:
    """e.g. "GSTR-3B (Q1 2026-27)" or "Form 138 (earlier 24Q) (Q2 2026-27)", for messages."""
    return f"{form_name(filing.form_code, filing.fy)} ({filing.period_label})"


# --- Peer insights and the admin's numbers --------------------------------------------


def filed_on_time(filing: ComplianceItem) -> bool:
    """Filed on or before its due date, in Indian time."""
    filed_day = filing.filed_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
    return filed_day <= filing.due_date


def peer_insights(business, filing: ComplianceItem) -> dict:
    """How businesses like this one file this form: the share filed by the business itself
    and through a CA, and how often each path was on time.

    The group is the businesses with the same entity type and MSME tier ("segment"), shown
    only when at least MIN_PEER_BUSINESSES of them filed the form; otherwise every business
    ("overall"), or nothing ("none") when even those are too few.
    """
    tier = onboarding.get_msme_tier(business)
    groups = []
    if tier is not None:
        groups.append(("segment", onboarding.business_ids_in_segment(business.entity_type, tier)))
    groups.append(("overall", None))

    result = {
        "form_code": filing.form_code,
        "scope": "none",
        "entity_type": business.entity_type,
        "msme_tier": tier,
        "min_businesses": MIN_PEER_BUSINESSES,
        "business_count": 0,
        "filing_count": 0,
        "self": None,
        "ca": None,
    }
    for scope, business_ids in groups:
        stmt = select(ComplianceItem).where(
            ComplianceItem.form_code == filing.form_code,
            ComplianceItem.status.in_(DONE_STATUSES),
            ComplianceItem.filed_at.is_not(None),
        )
        if business_ids is not None:
            stmt = stmt.where(ComplianceItem.business_id.in_(business_ids))
        filed = list(db.session.scalars(stmt))
        businesses = {item.business_id for item in filed}
        if len(businesses) < MIN_PEER_BUSINESSES:
            continue
        paths = {
            "self": [item for item in filed if item.filing_path == FilingPath.SELF],
            "ca": [item for item in filed if item.filing_path == FilingPath.CA],
        }
        total = len(paths["self"]) + len(paths["ca"])
        result.update(scope=scope, business_count=len(businesses), filing_count=total)
        for name, items in paths.items():
            on_time = sum(1 for item in items if filed_on_time(item))
            result[name] = {
                "count": len(items),
                "share_pct": round(len(items) * 100 / total) if total else None,
                "on_time_pct": round(on_time * 100 / len(items)) if items else None,
            }
        break
    return result


def filing_stats(today: date | None = None) -> dict:
    """For the admin dashboard: live filings by status, and the overdue rate: of the
    filings whose due date has passed, the share not filed on time (still unfiled, or filed
    after the due date), in percent (None before anything was due)."""
    today = today or today_in_india()
    by_status = {status.value: 0 for status in ComplianceStatus}
    due = 0
    late = 0
    for filing in db.session.scalars(select(ComplianceItem)):
        by_status[filing.status] += 1
        if filing.due_date < today:
            due += 1
            done = filing.status in DONE_STATUSES and filing.filed_at is not None
            if not done or not filed_on_time(filing):
                late += 1
    return {
        "filings_by_status": by_status,
        "filings_due_so_far": due,
        "filings_late": late,
        "overdue_rate": round(late * 100 / due, 1) if due else None,
    }


# --- Routes ------------------------------------------------------------------------------


def read_acknowledgement_no() -> str | None:
    """The optional ARN of a mark-filed form (up to 50 characters), in capitals."""
    acknowledgement_no = request.form.get("acknowledgement_no")
    if acknowledgement_no is None:
        return None
    if len(acknowledgement_no) > 50:
        raise validation_error({"acknowledgement_no": ["Longer than maximum length 50."]}, "form")
    return acknowledgement_no.strip().upper() or None


def own_filing(business, item_id) -> ComplianceItem:
    """One filing of this business. 404 FILING_NOT_FOUND for anyone else's."""
    filing = db.session.get(ComplianceItem, item_id)
    if filing is None or filing.business_id != business.id:
        raise ApiError(404, "FILING_NOT_FOUND", "This filing was not found.")
    return filing


@bp.get("/compliance/dashboard")
@roles_required(UserRole.BUSINESS)
def dashboard():
    """The business home page: next deadline and counts (just the welcome before registering)."""
    result = get_dashboard(current_user(), current_business_or_none())
    if result["next_deadline"] is not None:
        result["next_deadline"] = filing_to_dict(result["next_deadline"])
    return jsonify(result)


@bp.get("/compliance/items")
@roles_required(UserRole.BUSINESS)
def list_items():
    """The business's filings, soonest due first, optionally filtered by status, form and
    due dates (from / to, inclusive)."""
    errors = {}
    filters = {}
    status = request.args.get("status")
    if status is not None:
        if status not in list(ComplianceStatus):
            errors["status"] = [f"Must be one of: {', '.join(ComplianceStatus)}."]
        filters["status"] = status
    form_code = request.args.get("form_code")
    if form_code is not None:
        if form_code not in list(FormCode):
            errors["form_code"] = [f"Must be one of: {', '.join(FormCode)}."]
        filters["form_code"] = form_code
    for field in ("due_from", "due_to"):
        text = request.args.get(field)
        if text is not None:
            try:
                filters[field] = date.fromisoformat(text)
            except ValueError:
                errors[field] = ["Not a valid date."]
    if errors:
        raise validation_error(errors, "query")
    filings = list_filings(current_business(), **filters)
    return jsonify([filing_to_dict(filing) for filing in filings])


@bp.get("/compliance/items/<uuid:item_id>")
@roles_required(UserRole.BUSINESS)
def get_item(item_id):
    return jsonify(filing_page(own_filing(current_business(), item_id)))


@bp.post("/compliance/items/<uuid:item_id>/path")
@roles_required(UserRole.BUSINESS)
def choose_path(item_id):
    """The business files it itself ("self") or with a CA ("ca")."""
    path = json_body().get("path")
    if path is None:
        raise validation_error({"path": [MISSING]})
    if path not in list(FilingPath):
        raise validation_error({"path": [f"Must be one of: {', '.join(FilingPath)}."]})
    filing = own_filing(current_business(), item_id)
    if filing.status not in SELF_FILEABLE_STATUSES:
        raise ApiError(409, "FILING_LOCKED", "This filing is already with a CA or filed.")
    filing.filing_path = path
    db.session.commit()
    return jsonify(filing_page(filing))


@bp.post("/compliance/items/<uuid:item_id>/checklist")
@roles_required(UserRole.BUSINESS)
def tick_checklist(item_id):
    """Tick or untick one document of the checklist; the status follows."""
    data = json_body()
    errors = {}
    key = data.get("key")
    if key is None:
        errors["key"] = [MISSING]
    elif not isinstance(key, str) or not 1 <= len(key) <= 50:
        errors["key"] = ["Length must be between 1 and 50."]
    ticked = data.get("ticked")
    if ticked is None:
        errors["ticked"] = [MISSING]
    elif not isinstance(ticked, bool):
        errors["ticked"] = ["Not a valid boolean."]
    if errors:
        raise validation_error(errors)
    filing = own_filing(current_business(), item_id)
    _set_tick(filing, key, ticked)
    db.session.commit()
    return jsonify(filing_page(filing))


@bp.post("/compliance/items/<uuid:item_id>/mark-filed")
@roles_required(UserRole.BUSINESS)
def mark_filed(item_id):
    """The business filed it itself on the government portal (multipart/form-data): an
    optional ARN and an optional acknowledgement file, stored encrypted."""
    acknowledgement_no = read_acknowledgement_no()
    business = current_business()
    user = current_user()
    filing = own_filing(business, item_id)
    if filing.status == ComplianceStatus.WITH_CA:
        raise ApiError(409, "FILING_WITH_CA", "Your CA is handling this filing.")
    if filing.status not in SELF_FILEABLE_STATUSES:
        raise ApiError(409, "ALREADY_FILED", "This filing is already marked as filed.")
    upload = request.files.get("file")
    _record_filed(filing, user.id, user, FilingPath.SELF, acknowledgement_no, upload)
    db.session.commit()
    log.info("Filing %s marked filed by its business", filing.id)
    return jsonify(filing_page(filing))


@bp.post("/compliance/items/<uuid:item_id>/unmark-filed")
@roles_required(UserRole.BUSINESS)
def unmark_filed(item_id):
    """Undo a mistaken "mark as filed": the status is worked out again and the
    acknowledgement is deleted. Only for filings the business marked itself."""
    filing = own_filing(current_business(), item_id)
    if filing.status not in DONE_STATUSES or filing.filing_path != FilingPath.SELF:
        raise ApiError(409, "NOT_SELF_FILED", "Only a filing you marked as filed can be undone.")
    old_document_id = filing.acknowledgement_document_id
    filing.acknowledgement_document_id = None
    if old_document_id is not None:
        db.session.flush()  # the filing lets go of the file before the file is deleted
        documents.remove_document(old_document_id)
    filing.acknowledgement_no = None
    filing.filed_at = None
    filing.verified_at = None
    filing.status = ComplianceStatus.UPCOMING
    _refresh_status(filing, today_in_india())
    db.session.commit()
    return jsonify(filing_page(filing))


@bp.get("/compliance/items/<uuid:item_id>/acknowledgement")
@roles_required(UserRole.BUSINESS)
def get_acknowledgement(item_id):
    """The acknowledgement file the business uploaded."""
    filing = own_filing(current_business(), item_id)
    if filing.acknowledgement_document_id is None:
        raise ApiError(404, "ACKNOWLEDGEMENT_MISSING", "No acknowledgement was uploaded.")
    document, data = documents.read_document(filing.acknowledgement_document_id)
    return send_file(
        io.BytesIO(data), mimetype=document.mime_type, download_name=document.original_filename
    )


@bp.get("/compliance/items/<uuid:item_id>/peer-insights")
@roles_required(UserRole.BUSINESS)
def get_peer_insights(item_id):
    business = current_business()
    return jsonify(peer_insights(business, own_filing(business, item_id)))


@bp.get("/compliance/forms/<string:form_code>")
@login_required
def get_form(form_code):
    """A form's explanation, self-filing instructions and document checklist."""
    return jsonify(get_form_content(form_code))
