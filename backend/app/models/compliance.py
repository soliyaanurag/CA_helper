"""Compliance tables: how each form applies, and the filings of each business.

    obligation_templates  how a form applies and when it is due (ObligationTemplate)
    compliance_items      one filing of one business for one period (ComplianceItem)
    checklist_ticks       a ticked document-checklist entry of a filing (ChecklistTick)

Checklist entries, explanations and instructions stay in files
(content/forms/<FORM>/checklist.yaml ...); a tick stores only the entry's key.
Status lifecycle: upcoming -> docs_pending -> ready -> with_ca -> filed -> filed_verified,
plus overdue from any state before filed.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.enums import FormCode, str_enum


class Frequency(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class ComplianceStatus(StrEnum):
    UPCOMING = "upcoming"
    DOCS_PENDING = "docs_pending"
    READY = "ready"
    WITH_CA = "with_ca"
    FILED = "filed"
    FILED_VERIFIED = "filed_verified"
    OVERDUE = "overdue"


class FilingPath(StrEnum):
    SELF = "self"
    CA = "ca"


class ObligationTemplate(BaseModel):
    """How one form applies and when it is due, valid for a period (reference data, rule 3).

    GSTR-1 monthly and GSTR-1 quarterly (QRMP) are two templates of the same form.
    """

    __tablename__ = "obligation_templates"
    __table_args__ = (
        UniqueConstraint("form_code", "frequency", "effective_from"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from", name="valid_period"
        ),
    )

    form_code: Mapped[FormCode] = mapped_column(str_enum(FormCode))
    name: Mapped[str] = mapped_column(String(100))
    frequency: Mapped[Frequency] = mapped_column(str_enum(Frequency))
    # Which profiles it applies to, e.g. {"gst_scheme": ["regular_monthly"]}.
    applicability: Mapped[dict] = mapped_column(JSONB)
    # How to compute the due date, e.g. {"day": 11, "month_offset": 1}.
    due_date_rule: Mapped[dict] = mapped_column(JSONB)
    source_reference: Mapped[str] = mapped_column(String(500))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)


class ComplianceItem(BaseModel):
    """One filing of one business for one period, e.g. GSTR-3B for April 2026."""

    __tablename__ = "compliance_items"
    __table_args__ = (
        # One filing per business, form and period.
        UniqueConstraint("business_id", "form_code", "period_start"),
        CheckConstraint("period_end >= period_start", name="valid_period"),
        CheckConstraint("fy ~ '^[0-9]{4}-[0-9]{2}$'", name="fy_format"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("obligation_templates.id"))
    form_code: Mapped[FormCode] = mapped_column(str_enum(FormCode))
    fy: Mapped[str] = mapped_column(String(7))  # financial year, e.g. "2026-27"
    period_label: Mapped[str] = mapped_column(String(30))  # e.g. "Apr 2026", "Q1 2026-27"
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[ComplianceStatus] = mapped_column(
        str_enum(ComplianceStatus), default=ComplianceStatus.UPCOMING
    )
    # Self-filing or through a CA; empty until the business chooses.
    filing_path: Mapped[FilingPath | None] = mapped_column(str_enum(FilingPath))
    is_nil_return: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledgement_no: Mapped[str | None] = mapped_column(String(50))  # ARN / ack number
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledgement_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id")
    )


class ChecklistTick(BaseModel):
    """A ticked checklist entry of one filing. Unticking deletes the row (not soft)."""

    __tablename__ = "checklist_ticks"
    __table_args__ = (UniqueConstraint("compliance_item_id", "checklist_key"),)

    compliance_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compliance_items.id"))
    # A key from content/forms/<FORM>/checklist.yaml, e.g. "sales_register".
    checklist_key: Mapped[str] = mapped_column(String(50))
