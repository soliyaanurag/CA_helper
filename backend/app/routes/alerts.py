"""HTTP routes for alerts: /api/v1/alerts/...

    GET  /alerts/notifications?page=           my tray, newest first (every role)
    GET  /alerts/notifications/unread-count    {"unread": n} for the bell
    POST /alerts/notifications/<id>/read       mark one entry read
    POST /alerts/notifications/read-all        mark every entry read
    GET  /alerts/settings                      my email on/off per type (business, CA)
    PUT  /alerts/settings                      save them
    GET  /alerts/penalties                     late fees of my overdue filings (business)
    GET  /alerts/penalties/<item_id>?tax_due=  one filing's penalty estimate (business)

The reminder job also runs on demand: `flask alerts send-reminders [--date YYYY-MM-DD]`.

Routes stay thin: parse input (app/schemas/), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

import click
from flask_smorest import Blueprint

from app.errors import ErrorSchema
from app.models.enums import UserRole
from app.schemas.alerts import (
    NotificationArgsSchema,
    NotificationPageSchema,
    NotificationSchema,
    NotificationSettingsSchema,
    PenaltyArgsSchema,
    PenaltyEstimateSchema,
    PenaltyExposureSchema,
    UnreadCountSchema,
)
from app.services import alerts_service
from app.utils.decorators import current_business, current_user, login_required, roles_required

blp = Blueprint(
    "alerts",
    __name__,
    description="Notification tray, email settings, reminders and the penalty estimator",
)


@blp.route("/alerts/notifications", methods=["GET"])
@login_required
@blp.arguments(NotificationArgsSchema, location="query")
@blp.response(200, NotificationPageSchema)
def list_notifications(args):
    return alerts_service.list_notifications(current_user(), args["page"], args["page_size"])


@blp.route("/alerts/notifications/unread-count", methods=["GET"])
@login_required
@blp.response(200, UnreadCountSchema)
def unread_count():
    return alerts_service.unread_count(current_user())


@blp.route("/alerts/notifications/<uuid:notification_id>/read", methods=["POST"])
@login_required
@blp.response(200, NotificationSchema)
@blp.alt_response(404, schema=ErrorSchema, description="NOTIFICATION_NOT_FOUND")
def mark_read(notification_id):
    return alerts_service.mark_read(current_user(), notification_id)


@blp.route("/alerts/notifications/read-all", methods=["POST"])
@login_required
@blp.response(200, UnreadCountSchema)
def mark_all_read():
    return alerts_service.mark_all_read(current_user())


@blp.route("/alerts/settings", methods=["GET"])
@roles_required(UserRole.BUSINESS, UserRole.CA)
@blp.response(200, NotificationSettingsSchema)
def get_settings():
    return alerts_service.get_settings(current_user())


@blp.route("/alerts/settings", methods=["PUT"])
@roles_required(UserRole.BUSINESS, UserRole.CA)
@blp.arguments(NotificationSettingsSchema)
@blp.response(200, NotificationSettingsSchema)
def save_settings(data):
    return alerts_service.save_settings(current_user(), data["items"])


@blp.route("/alerts/penalties", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, PenaltyExposureSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND (register first)")
def penalty_exposure():
    return alerts_service.penalty_exposure(current_business())


@blp.route("/alerts/penalties/<uuid:item_id>", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(PenaltyArgsSchema, location="query")
@blp.response(200, PenaltyEstimateSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND, FILING_NOT_FOUND")
def estimate_penalty(args, item_id):
    return alerts_service.estimate_penalty(current_business(), item_id, args.get("tax_due"))


# `flask alerts send-reminders [--date 2026-10-06]`: run the daily reminder job now, for
# demos and testing. --date runs it as if it were that day (the reminders it records then
# count as sent, so the real day sends them no second time).
@blp.cli.command("send-reminders")
@click.option("--date", "day", type=click.DateTime(formats=["%Y-%m-%d"]), help="YYYY-MM-DD")
def send_reminders_command(day):
    """Send the deadline and overdue reminders now (what the worker does every morning)."""
    count = alerts_service.send_reminders(day.date() if day else None)
    click.echo(f"Recorded {count} reminder(s).")
