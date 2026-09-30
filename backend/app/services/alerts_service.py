"""Business logic for alerts: the notification tray, email settings, reminders, penalties.

notify(user, type, title, body, link, email) -> Notification   add a tray entry (+ email) (AL1)
queue_email(to, subject, template, **context)          send an email once the commit succeeds
list_notifications(user, page, page_size) -> dict      the user's tray, newest first
unread_count(user) -> dict                             {"unread": n}
mark_read(user, notification_id) -> Notification       one entry read
mark_all_read(user) -> dict                            every entry read -> {"unread": 0}
get_settings(user) / save_settings(user, items)        email on/off per type (AL3)
send_reminders(today) -> int                           worker job: T-7/T-3/T-1/overdue (AL2)
estimate_penalty(business, item_id, tax_due) -> dict   one filing's late fee + interest (AL5)
penalty_exposure(business) -> dict                     late fees of all overdue filings (AL5)

Tray entries are always created. Emails from notify() follow the user's settings for
the CONFIGURABLE_TYPES; engagement and account emails are transactional and always sent
(marketplace and auth send them themselves).

Emails and the single commit: notify() and queue_email() do not send at once. They put
the email in a list on the database session, and the two listeners at the bottom of this
file send the list after the caller's commit succeeds (or drop it on a rollback). So a
service still commits once, and nobody is emailed about something that was not saved.

Penalties are data (CLAUDE.md rule 3): `penalty_rules` rows, matched by form code and the
filing's due date. An amount that is not confirmed yet is empty (NULL) and skipped: the
estimate then says what is missing instead of showing a number.
"""

import logging
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import event, func, or_, select, update
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.extensions import db
from app.models import Notification, NotificationSetting, PenaltyRule, ReminderLog, User
from app.models.alerts import NotificationType, ReminderKind
from app.models.base import today_in_india, utcnow
from app.services import compliance_service, marketplace_service, onboarding_service
from app.utils.email import send_email

log = logging.getLogger(__name__)

# Types whose emails a user can switch off. The others (engagement updates, account
# emails) are always emailed: they answer something the user did.
CONFIGURABLE_TYPES = (
    NotificationType.DEADLINE_REMINDER,
    NotificationType.OVERDUE,
    NotificationType.DOCUMENT_REQUEST,
    NotificationType.REGULATORY_UPDATE,
)
ALWAYS_EMAILED_TYPES = (NotificationType.ENGAGEMENT_UPDATE, NotificationType.ACCOUNT)


# --- Emails sent after the commit -------------------------------------------------------

_EMAIL_QUEUE = "alerts_email_queue"  # key in the session's `info` dict


def queue_email(to: str, subject: str, template: str, **context) -> None:
    """Send this email (app/utils/email.py) once the current transaction commits; drop it
    if the transaction is rolled back. Does not commit."""
    db.session.info.setdefault(_EMAIL_QUEUE, []).append((to, subject, template, context))


@event.listens_for(Session, "after_commit")
def _send_queued_emails(session) -> None:
    for to, subject, template, context in session.info.pop(_EMAIL_QUEUE, []):
        send_email(to, subject, template, **context)


@event.listens_for(Session, "after_rollback")
def _drop_queued_emails(session) -> None:
    session.info.pop(_EMAIL_QUEUE, None)


# --- The tray (AL1) ----------------------------------------------------------------------


def wants_email(user_id, notification_type: NotificationType) -> bool:
    """Whether the user gets emails of this type (no settings row = yes)."""
    if notification_type not in CONFIGURABLE_TYPES:
        return True
    enabled = db.session.scalar(
        select(NotificationSetting.email_enabled).where(
            NotificationSetting.user_id == user_id,
            NotificationSetting.type == notification_type,
        )
    )
    return enabled is None or enabled


def notify(
    user: User,
    notification_type: NotificationType,
    title: str,
    body: str,
    link: str | None = None,
    email: bool = False,
) -> Notification:
    """Add a tray entry for `user`. With email=True, also email it after the caller's
    commit, unless the user switched this type off. Does not commit.

    `link` is an app path such as "/business/compliance/<id>". Never put PAN, GSTIN or
    other sensitive fields in the title or body.
    """
    notification = Notification(
        user_id=user.id, type=notification_type, title=title, body=body, link=link
    )
    db.session.add(notification)
    if email and user.is_active and wants_email(user.id, notification_type):
        queue_email(user.email, title, "notification", name=user.full_name, title=title, body=body)
    return notification


def _tray(user: User):
    """The user's live (not dismissed) tray entries."""
    return select(Notification).where(
        Notification.user_id == user.id, Notification.deleted_at.is_(None)
    )


def list_notifications(user: User, page: int, page_size: int) -> dict:
    """The user's tray, newest first. Paginated: {items, page, page_size, total}."""
    stmt = _tray(user).order_by(Notification.created_at.desc(), Notification.id)
    result = db.paginate(stmt, page=page, per_page=page_size, error_out=False)
    return {"items": result.items, "page": page, "page_size": page_size, "total": result.total}


def unread_count(user: User) -> dict:
    stmt = select(func.count()).select_from(
        _tray(user).where(Notification.read_at.is_(None)).subquery()
    )
    return {"unread": db.session.scalar(stmt)}


def mark_read(user: User, notification_id) -> Notification:
    """Mark one of the user's entries read (again is fine). 404 NOTIFICATION_NOT_FOUND."""
    notification = db.session.scalar(_tray(user).where(Notification.id == notification_id))
    if notification is None:
        raise ApiError(404, "NOTIFICATION_NOT_FOUND", "This notification was not found.")
    if notification.read_at is None:
        notification.read_at = utcnow()
    db.session.commit()
    return notification


def mark_all_read(user: User) -> dict:
    db.session.execute(
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.deleted_at.is_(None),
            Notification.read_at.is_(None),
        )
        .values(read_at=utcnow())
    )
    db.session.commit()
    return {"unread": 0}


# --- Email settings (AL3) ----------------------------------------------------------------


def get_settings(user: User) -> dict:
    """{items: [{type, email_enabled}] for each configurable type, always_emailed: [types]}."""
    saved = {}
    for row in db.session.scalars(
        select(NotificationSetting).where(NotificationSetting.user_id == user.id)
    ):
        saved[row.type] = row.email_enabled
    items = []
    for notification_type in CONFIGURABLE_TYPES:
        items.append(
            {"type": notification_type, "email_enabled": saved.get(notification_type, True)}
        )
    return {"items": items, "always_emailed": list(ALWAYS_EMAILED_TYPES)}


def save_settings(user: User, items: list[dict]) -> dict:
    """Save email on/off for the types in `items` (others keep their setting)."""
    for item in items:
        row = db.session.scalar(
            select(NotificationSetting).where(
                NotificationSetting.user_id == user.id,
                NotificationSetting.type == item["type"],
            )
        )
        if row is None:
            row = NotificationSetting(user_id=user.id, type=item["type"])
            db.session.add(row)
        row.email_enabled = item["email_enabled"]
    db.session.commit()
    return get_settings(user)


# --- Reminders (AL2): run by the worker, see backend/worker.py ---------------------------

# (kind, fewest days left, most days left). Windows instead of exact days: if the worker
# did not run on the 7th day before, the reminder still goes out on the 6th, 5th or 4th.
# Only the current window's reminder is sent; one that was missed is not sent late.
REMINDER_WINDOWS = (
    (ReminderKind.T_MINUS_7, 4, 7),
    (ReminderKind.T_MINUS_3, 2, 3),
    (ReminderKind.T_MINUS_1, 0, 1),
)
REMIND_DAYS_AHEAD = 7


def reminder_kind(days_left: int) -> ReminderKind | None:
    """Which reminder is due for a filing `days_left` days before its due date (negative
    = late), or None."""
    if days_left < 0:
        return ReminderKind.OVERDUE
    for kind, fewest, most in REMINDER_WINDOWS:
        if fewest <= days_left <= most:
            return kind
    return None


def _day_text(day: date) -> str:
    return f"{day.day} {day:%b %Y}"  # "20 Sep 2026"


def _reminder_title(filing, days_left: int) -> str:
    name = compliance_service.filing_name(filing)
    if days_left < 0:
        return f"{name} is overdue"
    if days_left == 0:
        return f"{name} is due today"
    if days_left == 1:
        return f"{name} is due tomorrow"
    return f"{name} is due in {days_left} days"


def _registered_on(business) -> date:
    """The Indian date the business registered."""
    return business.created_at.astimezone(ZoneInfo("Asia/Kolkata")).date()


def send_reminders(today: date | None = None) -> int:
    """Remind businesses (and the CA working on it) of filings due soon or overdue.
    Returns how many reminders were recorded. Runs daily; running it again the same day
    sends nothing new.

    - Each filing gets each kind (T-7, T-3, T-1, overdue) at most once (reminder_log).
    - A filing due before the business registered gets no reminder.
    - Every reminder is a tray entry; each person then gets ONE summary email for the
      run, listing the reminders whose type they have not switched off.
    """
    if today is None:
        today = today_in_india()
    last_day = today + timedelta(days=REMIND_DAYS_AHEAD)
    filings = compliance_service.list_unfiled_filings_due_by(last_day)
    filing_ids = [filing.id for filing in filings]
    already_sent = set()
    if filing_ids:
        rows = db.session.execute(
            select(ReminderLog.compliance_item_id, ReminderLog.kind).where(
                ReminderLog.compliance_item_id.in_(filing_ids)
            )
        )
        for filing_id, kind in rows:
            already_sent.add((filing_id, kind))
    ca_users = marketplace_service.active_ca_users_by_filing(filing_ids)

    emails = {}  # user id -> (user, [(title, body) for the summary email])
    count = 0
    for filing in filings:
        days_left = (filing.due_date - today).days
        kind = reminder_kind(days_left)
        if kind is None or (filing.id, kind) in already_sent:
            continue
        business = onboarding_service.get_business(filing.business_id)
        if business is None or business.deleted_at is not None:
            continue
        if filing.due_date < _registered_on(business):
            continue

        db.session.add(ReminderLog(compliance_item_id=filing.id, kind=kind, sent_at=utcnow()))
        count += 1
        if kind == ReminderKind.OVERDUE:
            notification_type = NotificationType.OVERDUE
            body = f"It was due on {_day_text(filing.due_date)}. File it as soon as you can."
        else:
            notification_type = NotificationType.DEADLINE_REMINDER
            body = f"Due on {_day_text(filing.due_date)}."
        title = _reminder_title(filing, days_left)

        recipients = [
            (db.session.get(User, business.user_id), title, f"/business/compliance/{filing.id}")
        ]
        ca_user = ca_users.get(filing.id)
        if ca_user is not None:
            recipients.append(
                (ca_user, f"{business.legal_name}: {title}", f"/ca/clients/{business.id}")
            )
        for user, user_title, link in recipients:
            if not user.is_active or user.deleted_at is not None:
                continue
            notify(user, notification_type, user_title, body, link)
            if wants_email(user.id, notification_type):
                emails.setdefault(user.id, (user, []))[1].append((user_title, body))

    for user, reminders in emails.values():
        subject = reminders[0][0]
        if len(reminders) > 1:
            subject = f"{len(reminders)} filings need your attention"
        lines = [f"{title}. {body}" for title, body in reminders]
        queue_email(user.email, subject, "reminders", name=user.full_name, lines=lines)
    db.session.commit()
    if count > 0:
        log.info("Recorded %d reminder(s), emailed %d person(s)", count, len(emails))
    return count


# --- Penalty estimator (AL5) ----------------------------------------------------------------

LABEL_PENDING = "Estimate (rules pending verification)"
LABEL_VERIFIED = "Estimate"
CENT = Decimal("0.01")


def _rule_for(form_code, day: date) -> PenaltyRule | None:
    """The penalty rule of a form in force on `day` (the filing's due date)."""
    return db.session.scalar(
        select(PenaltyRule)
        .where(
            PenaltyRule.form_code == form_code,
            PenaltyRule.effective_from <= day,
            or_(PenaltyRule.effective_to.is_(None), PenaltyRule.effective_to > day),
        )
        .order_by(PenaltyRule.effective_from.desc())
    )


def _late_fee(rule: PenaltyRule, filing, days_late: int) -> Decimal | None:
    """A flat fee if the rule has one, else days × the daily fee (the nil-return fee for a
    nil return, when set), capped at the maximum. None when the amounts are not confirmed."""
    if rule.flat_late_fee is not None:
        return rule.flat_late_fee
    per_day = rule.late_fee_per_day
    if filing.is_nil_return and rule.nil_return_late_fee_per_day is not None:
        per_day = rule.nil_return_late_fee_per_day
    if per_day is None:
        return None
    fee = per_day * days_late
    if rule.max_late_fee is not None:
        fee = min(fee, rule.max_late_fee)
    return fee.quantize(CENT, rounding=ROUND_HALF_UP)


def _estimate(filing, today: date, tax_due: Decimal | None) -> dict:
    """The estimate for one filing (see estimate_penalty)."""
    days_late = max((today - filing.due_date).days, 0)
    result = {
        "compliance_item_id": filing.id,
        "form_code": filing.form_code,
        "period_label": filing.period_label,
        "due_date": filing.due_date,
        "days_late": days_late,
        "status": "estimated",
        "late_fee": None,
        "interest": None,
        "total": None,
        "notes": [],
        "label": LABEL_PENDING,
    }
    if filing.status in compliance_service.DONE_STATUSES:
        result.update(status="filed", days_late=0)
        return result
    if days_late == 0:
        result["status"] = "not_late"
        return result

    rule = _rule_for(filing.form_code, filing.due_date)
    if rule is None:
        result.update(status="pending", notes=["There is no penalty rule for this form yet."])
        return result
    if "TODO_VERIFY" not in rule.source_reference:
        result["label"] = LABEL_VERIFIED

    result["late_fee"] = _late_fee(rule, filing, days_late)
    if result["late_fee"] is None:
        result["notes"].append("The late fee for this form is not confirmed yet.")
    if rule.annual_interest_rate is None:
        result["notes"].append("The interest rate is not confirmed yet.")
    elif tax_due is None:
        result["notes"].append("Enter the tax due to estimate the interest.")
    else:
        interest = tax_due * rule.annual_interest_rate / 100 * days_late / 365
        result["interest"] = interest.quantize(CENT, rounding=ROUND_HALF_UP)

    amounts = [amount for amount in (result["late_fee"], result["interest"]) if amount is not None]
    if amounts:
        result["total"] = sum(amounts)
    else:
        result["status"] = "pending"
    return result


def estimate_penalty(business, item_id, tax_due: Decimal | None = None, today=None) -> dict:
    """The late fee (and interest, when `tax_due` is given) of one of the business's filings
    as of today, using the penalty rule in force on its due date.

    `status`: "not_late", "filed", "estimated" (at least one amount) or "pending" (late, but
    no confirmed amount); `notes` say what is missing. 404 FILING_NOT_FOUND.
    """
    filing = compliance_service.get_filings_by_ids([item_id]).get(item_id)
    if filing is None or filing.business_id != business.id:
        raise ApiError(404, "FILING_NOT_FOUND", "This filing was not found.")
    return _estimate(filing, today or today_in_india(), tax_due)


def penalty_exposure(business, today=None) -> dict:
    """The late fees of all the business's overdue (late, not filed) filings, for the
    dashboard. Interest is not included (it needs each filing's tax amount)."""
    today = today or today_in_india()
    items = []
    total = Decimal("0.00")
    estimated = 0
    for filing in compliance_service.list_filings(business):
        if filing.status in compliance_service.DONE_STATUSES or filing.due_date >= today:
            continue
        estimate = _estimate(filing, today, None)
        items.append(estimate)
        if estimate["late_fee"] is not None:
            total += estimate["late_fee"]
            estimated += 1
    label = LABEL_PENDING
    if items and all(item["label"] == LABEL_VERIFIED for item in items):
        label = LABEL_VERIFIED
    return {
        "total_late_fees": total,
        "overdue_count": len(items),
        "estimated_count": estimated,
        "pending_count": len(items) - estimated,
        "label": label,
        "items": items,
    }
