"""Alert tables: the in-app tray, email preferences, sent reminders and penalty rules.

    notifications          one tray entry for one user (Notification)
    notification_settings  a user's email on/off per notification type (NotificationSetting)
    reminder_log           a reminder already sent for a filing (ReminderLog)
    penalty_rules          late fees and interest per form, versioned by dates (PenaltyRule)

A reminder is sent at most once per filing and kind (UNIQUE). Penalty rules are matched
by form code and date (no foreign key) and never invented (rule 3): an amount that is
not confirmed yet is left empty (NULL) and the estimator skips it.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class NotificationType(StrEnum):
    DEADLINE_REMINDER = "deadline_reminder"
    OVERDUE = "overdue"
    ENGAGEMENT_UPDATE = "engagement_update"
    DOCUMENT_REQUEST = "document_request"
    REGULATORY_UPDATE = "regulatory_update"
    ACCOUNT = "account"


class ReminderKind(StrEnum):
    T_MINUS_7 = "t_minus_7"
    T_MINUS_3 = "t_minus_3"
    T_MINUS_1 = "t_minus_1"
    OVERDUE = "overdue"


class Notification(BaseModel):
    """One entry in a user's notification tray."""

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(2000))
    link: Mapped[str | None] = mapped_column(
        String(300)
    )  # an app path, e.g. "/business/compliance"
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationSetting(BaseModel):
    """Whether a user gets emails of one notification type (no row = the default, on)."""

    __tablename__ = "notification_settings"
    __table_args__ = (UniqueConstraint("user_id", "type"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(50))
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ReminderLog(BaseModel):
    """A reminder already sent for one filing, so it is never sent twice."""

    __tablename__ = "reminder_log"
    __table_args__ = (UniqueConstraint("compliance_item_id", "kind"),)

    compliance_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compliance_items.id"))
    kind: Mapped[str] = mapped_column(String(50))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PenaltyRule(BaseModel):
    """Late fee and interest for one form, valid for a period (reference data, rule 3)."""

    __tablename__ = "penalty_rules"
    __table_args__ = (
        UniqueConstraint("form_code", "effective_from"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from", name="valid_period"
        ),
        CheckConstraint(
            "late_fee_per_day >= 0 AND annual_interest_rate >= 0"
            " AND (max_late_fee IS NULL OR max_late_fee >= 0)",
            name="amounts_not_negative",
        ),
        CheckConstraint(
            "flat_late_fee IS NULL OR flat_late_fee >= 0", name="flat_late_fee_not_negative"
        ),
    )

    # Every amount may be empty (NULL) while it is not confirmed from an official source.
    form_code: Mapped[str] = mapped_column(String(50))
    late_fee_per_day: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # rupees
    max_late_fee: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # empty = no cap
    # A fixed late fee, charged once however late (e.g. the ITR); used instead of the per-day fee.
    flat_late_fee: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    annual_interest_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # percent, e.g. 18
    source_reference: Mapped[str] = mapped_column(String(500))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
