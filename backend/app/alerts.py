"""Alerts: the notification tray and bell, the daily deadline reminders and the penalty
estimate.

Tray entries are always created. Emails go out only when the user's `email_notifications`
switch is on, and only after the caller's commit, so nobody is emailed about something
that was not saved.

Penalties are data: `penalty_rules` rows, matched by form code and the filing's due date.
An amount that is not confirmed yet is empty (NULL) and skipped: the estimate then says
what is missing instead of showing a number.
"""

import logging
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import click
from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, select, update

from app import compliance, marketplace, onboarding
from app.models import (
    Notification,
    NotificationType,
    PenaltyRule,
    ReminderKind,
    ReminderLog,
    User,
    UserRole,
    db,
    today_in_india,
    utcnow,
)
from app.utils import (
    ApiError,
    current_business,
    current_user,
    iso,
    login_required,
    money,
    read_page_args,
    roles_required,
    send_email,
    validation_error,
)

log = logging.getLogger(__name__)

bp = Blueprint("alerts", __name__)

MAX_TAX_DUE = Decimal(10**10)  # rupees; the estimate's input limit


# --- The tray ----------------------------------------------------------------------------


def notify(
    user: User,
    notification_type: NotificationType,
    title: str,
    body: str,
    link: str | None = None,
) -> Notification:
    """Add a tray entry for `user`. Does not commit.

    `link` is an app path such as "/business/compliance/<id>". Never put PAN, GSTIN or
    other sensitive fields in the title or body.
    """
    notification = Notification(
        user_id=user.id, type=notification_type, title=title, body=body, link=link
    )
    db.session.add(notification)
    return notification


def email_notice(user: User, title: str, body: str) -> None:
    """Email a tray entry's text to the user, if they want emails. Call after the commit."""
    if user.email_notifications:
        send_email(user.email, title, "notification", name=user.full_name, title=title, body=body)


def notification_to_dict(notification: Notification) -> dict:
    return {
        "id": str(notification.id),
        "type": notification.type,
        "title": notification.title,
        "body": notification.body,
        "link": notification.link,
        "read_at": iso(notification.read_at),
        "created_at": iso(notification.created_at),
    }


# --- Reminders (the worker runs send_reminders every morning) -----------------------------

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
    name = compliance.filing_name(filing)
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
    - Every reminder is a tray entry; each person who wants emails then gets ONE summary
      email for the run.
    """
    if today is None:
        today = today_in_india()
    last_day = today + timedelta(days=REMIND_DAYS_AHEAD)
    filings = compliance.list_unfiled_filings_due_by(last_day)
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
    ca_users = marketplace.active_ca_users_by_filing(filing_ids)

    emails = {}  # user id -> (user, [(title, body) for the summary email])
    count = 0
    for filing in filings:
        days_left = (filing.due_date - today).days
        kind = reminder_kind(days_left)
        if kind is None or (filing.id, kind) in already_sent:
            continue
        business = onboarding.get_business(filing.business_id)
        if business is None:
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
            notify(user, notification_type, user_title, body, link)
            if user.email_notifications:
                emails.setdefault(user.id, (user, []))[1].append((user_title, body))

    db.session.commit()
    for user, reminders in emails.values():
        subject = reminders[0][0]
        if len(reminders) > 1:
            subject = f"{len(reminders)} filings need your attention"
        lines = [f"{title}. {body}" for title, body in reminders]
        send_email(user.email, subject, "reminders", name=user.full_name, lines=lines)
    if count > 0:
        log.info("Recorded %d reminder(s), emailed %d person(s)", count, len(emails))
    return count


# --- Penalty estimate ------------------------------------------------------------------------

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


def _late_fee(rule: PenaltyRule, days_late: int) -> Decimal | None:
    """A flat fee if the rule has one, else days × the daily fee, capped at the maximum.
    None when the amounts are not confirmed."""
    if rule.flat_late_fee is not None:
        return rule.flat_late_fee
    per_day = rule.late_fee_per_day
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
    if filing.status in compliance.DONE_STATUSES:
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

    result["late_fee"] = _late_fee(rule, days_late)
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
    filing = compliance.get_filings_by_ids([item_id]).get(item_id)
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
    for filing in compliance.list_filings(business):
        if filing.status in compliance.DONE_STATUSES or filing.due_date >= today:
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


def estimate_to_dict(estimate: dict) -> dict:
    """An estimate from _estimate() as JSON: ids and dates as text, amounts as "1250.00"."""
    result = dict(estimate)
    result["compliance_item_id"] = str(estimate["compliance_item_id"])
    result["due_date"] = iso(estimate["due_date"])
    for key in ("late_fee", "interest", "total"):
        result[key] = money(estimate[key])
    return result


# --- Routes ------------------------------------------------------------------------------


def my_tray():
    """The logged-in user's tray entries."""
    return select(Notification).where(Notification.user_id == current_user().id)


@bp.get("/alerts/notifications")
@login_required
def list_notifications():
    """The user's tray, newest first, paginated."""
    errors = {}
    page, page_size = read_page_args(errors)
    if errors:
        raise validation_error(errors, "query")
    stmt = my_tray().order_by(Notification.created_at.desc(), Notification.id)
    result = db.paginate(stmt, page=page, per_page=page_size, error_out=False)
    return jsonify(
        {
            "items": [notification_to_dict(item) for item in result.items],
            "page": page,
            "page_size": page_size,
            "total": result.total,
        }
    )


@bp.get("/alerts/notifications/unread-count")
@login_required
def unread_count():
    unread = my_tray().where(Notification.read_at.is_(None)).subquery()
    return jsonify({"unread": db.session.scalar(select(func.count()).select_from(unread))})


@bp.post("/alerts/notifications/<uuid:notification_id>/read")
@login_required
def mark_read(notification_id):
    """Mark one of the user's entries read (again is fine)."""
    notification = db.session.scalar(my_tray().where(Notification.id == notification_id))
    if notification is None:
        raise ApiError(404, "NOTIFICATION_NOT_FOUND", "This notification was not found.")
    if notification.read_at is None:
        notification.read_at = utcnow()
    db.session.commit()
    return jsonify(notification_to_dict(notification))


@bp.post("/alerts/notifications/read-all")
@login_required
def mark_all_read():
    db.session.execute(
        update(Notification)
        .where(Notification.user_id == current_user().id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    db.session.commit()
    return jsonify({"unread": 0})


@bp.get("/alerts/penalties")
@roles_required(UserRole.BUSINESS)
def get_penalty_exposure():
    """The late fees of all the business's overdue filings, for the dashboard."""
    exposure = penalty_exposure(current_business())
    exposure["total_late_fees"] = money(exposure["total_late_fees"])
    exposure["items"] = [estimate_to_dict(item) for item in exposure["items"]]
    return jsonify(exposure)


@bp.get("/alerts/penalties/<uuid:item_id>")
@roles_required(UserRole.BUSINESS)
def get_penalty_estimate(item_id):
    """One filing's late fee, and its interest when ?tax_due= (unpaid tax, rupees) is given."""
    tax_due = request.args.get("tax_due")
    if tax_due is not None:
        try:
            tax_due = Decimal(tax_due).quantize(Decimal("0.01"))
        except InvalidOperation:
            raise validation_error({"tax_due": ["Not a valid number."]}, "query")
        if not 0 <= tax_due <= MAX_TAX_DUE:
            raise validation_error(
                {"tax_due": [f"Must be greater than or equal to 0 and less than or equal to {MAX_TAX_DUE}."]},
                "query",
            )
    return jsonify(estimate_to_dict(estimate_penalty(current_business(), item_id, tax_due)))


# `flask alerts send-reminders [--date 2026-10-06]`: run the daily reminder job now, for
# demos and testing. --date runs it as if it were that day (the reminders it records then
# count as sent, so the real day sends them no second time).
@bp.cli.command("send-reminders")
@click.option("--date", "day", type=click.DateTime(formats=["%Y-%m-%d"]), help="YYYY-MM-DD")
def send_reminders_command(day):
    """Send the deadline and overdue reminders now (what the worker does every morning)."""
    count = send_reminders(day.date() if day else None)
    click.echo(f"Recorded {count} reminder(s).")
