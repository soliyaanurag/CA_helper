"""Every database table, the shared column helpers and the encryption of sensitive values.
"""

import uuid
from datetime import date, datetime, UTC
from decimal import Decimal
from enum import StrEnum
from functools import cache
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    func,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


# Deterministic names for indexes and constraints, so migrations generated on different
# machines are identical.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base behind `db.Model`. Models subclass BaseModel below."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# SQLAlchemy 2.x style: models subclass db.Model, which uses our Base.
db = SQLAlchemy(model_class=Base)


# --- base --------------------------------------------------------------------------------


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime (CLAUDE.md rule 7)."""
    return datetime.now(UTC)


def today_in_india() -> date:
    """Today's date in India. Due dates and financial years are Indian dates."""
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


class TimestampMixin:
    """`created_at` and `updated_at`, stored as timezone-aware UTC.

    Python sets both on insert and `updated_at` on every ORM update; the
    database default `now()` covers rows inserted with raw SQL.
    Bulk `UPDATE` statements bypass `onupdate`, so set `updated_at` there yourself.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )


class BaseModel(TimestampMixin, db.Model):
    """Abstract base for every table: UUID primary key plus timestamps.

    The UUID is generated in Python (uuid4) and stored in Postgres's native
    `uuid` type; the API sends it as a string.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


# --- enums -------------------------------------------------------------------------------


class UserRole(StrEnum):
    """Who a login account belongs to; also the `role` claim in the JWT."""

    BUSINESS = "business"
    CA = "ca"
    ADMIN = "admin"


class FormCode(StrEnum):
    """The seven filings tracked in v1. Used by compliance, alerts, marketplace and
    regulatory tables; content lives in content/forms/<FORM>/."""

    ITR = "itr"
    GSTR_1 = "gstr_1"
    GSTR_3B = "gstr_3b"
    CMP_08 = "cmp_08"
    GSTR_4 = "gstr_4"
    TDS_24Q = "tds_24q"
    TDS_26Q = "tds_26q"


# --- encryption --------------------------------------------------------------------------


KEY_HELP = (
    "Generate one with:\n"
    "  conda run -n ca-helper python -c "
    '"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"\n'
    "and put it in .env as FIELD_ENCRYPTION_KEY=... (see .env.example)."
)


@cache
def _fernet_for(key: str) -> Fernet:
    try:
        return Fernet(key)
    except ValueError as error:
        raise RuntimeError(f"FIELD_ENCRYPTION_KEY is not a valid Fernet key. {KEY_HELP}") from error


def _fernet() -> Fernet:
    key = current_app.config.get("FIELD_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(f"FIELD_ENCRYPTION_KEY is not set. {KEY_HELP}")
    return _fernet_for(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt a file's contents (documents.content)."""
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _fernet().decrypt(token)
    except InvalidToken as error:
        raise RuntimeError(
            "A stored file cannot be decrypted: FIELD_ENCRYPTION_KEY is not the key it was "
            "encrypted with."
        ) from error


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as error:
        raise RuntimeError(
            "An encrypted value cannot be decrypted: FIELD_ENCRYPTION_KEY is not the key it was "
            "encrypted with."
        ) from error


class EncryptedString(TypeDecorator):
    """A text column stored encrypted. None stays None (NULL)."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt(value)

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt(value)


# --- user --------------------------------------------------------------------------------


class User(BaseModel):
    """A login account (business owner, CA or admin)."""

    __tablename__ = "users"

    # Stored normalized (trimmed, lowercased) by auth_service.normalize_email().
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))  # argon2, never the password
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(50))
    # Set when the user enters the code we emailed them; login is refused while it is empty.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When the user accepted the terms (set by signup in a later task; empty until then).
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The user's one switch for notification emails (codes and password emails always go out).
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


# --- email_otp ---------------------------------------------------------------------------


class OtpPurpose(StrEnum):
    """What a one-time code is for."""

    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"


class EmailOtp(BaseModel):
    """One code emailed to a user."""

    __tablename__ = "email_otps"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    user: Mapped[User] = relationship()
    purpose: Mapped[str] = mapped_column(String(50))
    code_hash: Mapped[str] = mapped_column(String(255))  # argon2 hash of the 6 digits
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Wrong guesses so far; the code stops working at auth_service.OTP_MAX_ATTEMPTS.
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --- onboarding --------------------------------------------------------------------------


class EntityType(StrEnum):
    INDIVIDUAL = "individual"  # freelancer / gig worker
    PROPRIETORSHIP = "proprietorship"
    PARTNERSHIP = "partnership"
    LLP = "llp"
    PRIVATE_LIMITED = "private_limited"


class MsmeTier(StrEnum):
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    NOT_MSME = "not_msme"


class GstScheme(StrEnum):
    NOT_REGISTERED = "not_registered"
    REGULAR_MONTHLY = "regular_monthly"
    REGULAR_QRMP = "regular_qrmp"
    COMPOSITION = "composition"


class ItrForm(StrEnum):
    ITR_3 = "itr_3"
    ITR_4 = "itr_4"
    ITR_5 = "itr_5"
    ITR_6 = "itr_6"


class NicCode(BaseModel):
    """One activity code from the official NIC list (reference data, imported, never invented)."""

    __tablename__ = "nic_codes"

    code: Mapped[str] = mapped_column(String(10), unique=True)
    description: Mapped[str] = mapped_column(String(500))


class Business(BaseModel):
    """A registered business: at most one business per business user."""

    __tablename__ = "businesses"
    __table_args__ = (
        CheckConstraint(
            "NOT gst_registered OR gstin IS NOT NULL", name="gstin_when_gst_registered"
        ),
        CheckConstraint("NOT deducts_tds OR tan IS NOT NULL", name="tan_when_deducts_tds"),
        CheckConstraint(
            "entity_type NOT IN ('llp', 'private_limited') OR cin_llpin IS NOT NULL",
            name="cin_llpin_for_llp_and_company",
        ),
        CheckConstraint(
            "annual_turnover >= 0 AND investment_amount >= 0", name="amounts_not_negative"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    legal_name: Mapped[str] = mapped_column(String(200))
    entity_type: Mapped[str] = mapped_column(String(50))
    state: Mapped[str] = mapped_column(String(50))  # Indian state or union territory
    address: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(String(1000))
    # Rupees, as declared by the business (an amount, not a range).
    annual_turnover: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Investment in plant, machinery and equipment, in rupees (drives the MSME tier).
    investment_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    pan: Mapped[str] = mapped_column(EncryptedString())
    phone: Mapped[str] = mapped_column(EncryptedString())
    gst_registered: Mapped[bool] = mapped_column(Boolean)
    gstin: Mapped[str | None] = mapped_column(EncryptedString())  # required when gst_registered
    # The business chose the GST composition scheme (a choice, so we ask; only if GST registered).
    gst_composition: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # A regular-scheme business within the QRMP limit chose quarterly returns (QRMP).
    gst_qrmp: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Partnerships and LLPs: their accounts are audited under another law (their answer).
    accounts_audited_other_law: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    deducts_tds: Mapped[bool] = mapped_column(Boolean)
    tan: Mapped[str | None] = mapped_column(EncryptedString())  # required when deducts_tds
    pays_salary_above_limit: Mapped[bool] = mapped_column(Boolean)
    # CIN (company) or LLPIN (LLP); required for those two entity types.
    cin_llpin: Mapped[str | None] = mapped_column(String(21))
    udyam_number: Mapped[str | None] = mapped_column(String(19))  # UDYAM-XX-00-0000000
    nic_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("nic_codes.id"))


class RegulatoryProfile(BaseModel):
    """The current computed profile of one business (recomputed in place, never versioned).

    `explanations` holds the "why" for every line, e.g. {"msme_tier": "Investment ... ≤ ..."}.
    """

    __tablename__ = "regulatory_profiles"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), unique=True)
    msme_tier: Mapped[str] = mapped_column(String(50))
    gst_scheme: Mapped[str] = mapped_column(String(50))
    # Not registered, but the rules suggest registering (e.g. turnover near the limit).
    gst_registration_suggested: Mapped[bool] = mapped_column(Boolean)
    itr_form: Mapped[str] = mapped_column(String(50))
    presumptive_eligible: Mapped[bool] = mapped_column(Boolean)
    # Tax audit under section 44AB (from turnover).
    audit_applicable: Mapped[bool] = mapped_column(Boolean)
    # Accounts audited under another law (companies always; partnerships and LLPs if they say so).
    # Either audit moves the ITR due date.
    other_audit_applicable: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    files_24q: Mapped[bool] = mapped_column(Boolean)
    files_26q: Mapped[bool] = mapped_column(Boolean)
    # LLPs and companies: ROC/MCA filings exist but are not tracked (a notice in the UI).
    roc_not_tracked: Mapped[bool] = mapped_column(Boolean)
    explanations: Mapped[dict] = mapped_column(JSONB)
    # Which set of rules produced it, so a rule change can trigger a recompute.
    rule_version: Mapped[str] = mapped_column(String(50))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RuleThreshold(BaseModel):
    """One legal threshold or value, valid from `effective_from` until `effective_to`.

    Unverified values carry TODO_VERIFY in source_reference (docs/TODO_VERIFY.md).
    """

    __tablename__ = "rule_thresholds"
    __table_args__ = (
        UniqueConstraint("key", "effective_from"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from", name="valid_period"
        ),
    )

    key: Mapped[str] = mapped_column(String(100))  # e.g. "gst_registration_limit_goods"
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit: Mapped[str] = mapped_column(String(20))  # e.g. "inr", "percent", "days"
    description: Mapped[str] = mapped_column(String(500))
    source_reference: Mapped[str] = mapped_column(String(500))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)  # empty = still in force


# --- compliance --------------------------------------------------------------------------


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

    form_code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(100))
    frequency: Mapped[str] = mapped_column(String(50))
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
    form_code: Mapped[str] = mapped_column(String(50))
    fy: Mapped[str] = mapped_column(String(7))  # financial year, e.g. "2026-27"
    period_label: Mapped[str] = mapped_column(String(30))  # e.g. "Apr 2026", "Q1 2026-27"
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(
        String(50), default=ComplianceStatus.UPCOMING
    )
    # Self-filing or through a CA; empty until the business chooses.
    filing_path: Mapped[str | None] = mapped_column(String(50))
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


# --- documents ---------------------------------------------------------------------------


class DocumentType(StrEnum):
    GST_CERTIFICATE = "gst_certificate"
    PAN_CARD = "pan_card"
    SALES_REGISTER = "sales_register"
    PURCHASE_REGISTER = "purchase_register"
    BANK_STATEMENT = "bank_statement"
    INVOICE = "invoice"
    SALARY_REGISTER = "salary_register"
    TDS_CHALLAN = "tds_challan"
    ACKNOWLEDGEMENT = "acknowledgement"
    CERTIFICATE_OF_PRACTICE = "certificate_of_practice"
    OTHER = "other"


class OcrStatus(StrEnum):
    NONE = "none"  # not run (yet)
    PROCESSED = "processed"
    FAILED = "failed"


class Document(BaseModel):
    """One uploaded file: its metadata and its encrypted contents."""

    __tablename__ = "documents"
    __table_args__ = (CheckConstraint("size_bytes >= 0", name="size_not_negative"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    doc_type: Mapped[str] = mapped_column(String(50))
    original_filename: Mapped[str] = mapped_column(String(255))
    # The file, encrypted. Deferred: loaded only when the file itself is read, not for lists.
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))  # of the original file
    fy: Mapped[str | None] = mapped_column(String(7))  # e.g. "2026-27"
    period_label: Mapped[str | None] = mapped_column(String(30))  # e.g. "Apr 2026"
    ocr_status: Mapped[str] = mapped_column(String(50), default=OcrStatus.NONE)
    # What OCR extracted, e.g. {"arn": "...", "filed_on": "2026-05-11"}.
    ocr_fields: Mapped[dict | None] = mapped_column(JSONB)


class ComplianceItemDocument(BaseModel):
    """A document serving a filing. One file can serve several filings.

    `checklist_key` is the checklist entry it answers, or "general". Unlinking deletes
    the row (not soft).
    """

    __tablename__ = "compliance_item_documents"
    __table_args__ = (
        UniqueConstraint("compliance_item_id", "document_id", "checklist_key"),
        CheckConstraint("checklist_key <> ''", name="checklist_key_not_empty"),
    )

    compliance_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("compliance_items.id"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    checklist_key: Mapped[str] = mapped_column(
        String(50), default="general", server_default="general"
    )
    linked_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


# --- alerts ------------------------------------------------------------------------------


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


# --- marketplace -------------------------------------------------------------------------


class CaVerificationStatus(StrEnum):
    """Where a CA profile is in the admin's check."""

    PENDING = "pending"  # saved by the CA, waiting for an admin
    VERIFIED = "verified"  # checked by an admin: listed in the marketplace
    REJECTED = "rejected"  # the admin could not confirm the numbers


# The work a CA can be tagged with: the seven forms we track, then broader areas.
CA_SPECIALIZATIONS = (
    "itr",
    "gstr_1",
    "gstr_3b",
    "cmp_08",
    "gstr_4",
    "tds_24q",
    "tds_26q",
    "gst_registration",
    "tax_audit",
    "accounting_bookkeeping",
    "income_tax_notices",
    "company_llp_compliance",
    "startup_msme_advisory",
)

# The specialization each catalog service (by code) belongs to. A CA who prices a service
# should have its specialization; the services page warns otherwise.
SERVICE_SPECIALIZATIONS = {
    "itr_presumptive": "itr",
    "itr_business": "itr",
    "itr_firm_company": "itr",
    "gstr_1": "gstr_1",
    "gstr_3b": "gstr_3b",
    "cmp_08": "cmp_08",
    "gstr_4": "gstr_4",
    "tds_24q": "tds_24q",
    "tds_26q": "tds_26q",
    "gst_registration": "gst_registration",
    "tax_audit": "tax_audit",
    "bookkeeping": "accounting_bookkeeping",
    "income_tax_notice": "income_tax_notices",
}

CA_LANGUAGES = (
    "english",
    "hindi",
    "bengali",
    "gujarati",
    "kannada",
    "malayalam",
    "marathi",
    "odia",
    "punjabi",
    "tamil",
    "telugu",
    "urdu",
)


class CaProfile(BaseModel):
    """One CA's practice profile (at most one per CA user)."""

    __tablename__ = "ca_profiles"
    __table_args__ = (
        Index("ix_ca_profiles_specializations", "specializations", postgresql_using="gin"),
        CheckConstraint("pro_bono_slots_per_month >= 0", name="pro_bono_slots_not_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    # foreign_keys: ca_profiles has two links to users (this one and verified_by_id).
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    # ICAI membership number: 6 digits (checked in app/schemas/marketplace.py).
    membership_no: Mapped[str] = mapped_column(String(6), unique=True)
    # Certificate of Practice number, typed by the CA (the certificate upload comes later).
    cop_number: Mapped[str] = mapped_column(String(20))
    city: Mapped[str] = mapped_column(String(100))
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(50)))
    specializations: Mapped[list[str]] = mapped_column(ARRAY(String(50)))
    # The most clients the CA wants to take on at the same time.
    capacity: Mapped[int] = mapped_column(Integer)
    years_experience: Mapped[int] = mapped_column(Integer)
    about: Mapped[str] = mapped_column(String(500), default="", server_default="")
    verification_status: Mapped[str] = mapped_column(
        String(50), default=CaVerificationStatus.PENDING
    )
    # Pro-bono engagements the CA pledges to take each month (0 = none).
    pro_bono_slots_per_month: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Set by the admin: why a profile was rejected; when and by whom it was verified.
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # The uploaded Certificate of Practice (a document owned by the CA's user).
    cop_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))


class ServiceUnit(StrEnum):
    """What one price of a catalog service pays for."""

    PER_RETURN = "per_return"
    PER_MONTH = "per_month"
    PER_YEAR = "per_year"
    ONE_TIME = "one_time"
    PER_NOTICE = "per_notice"


class CatalogService(BaseModel):
    """One standard service, e.g. "GSTR-3B filing", priced per return."""

    __tablename__ = "service_catalog"

    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(300))
    unit: Mapped[str] = mapped_column(String(50))
    # Services are listed in this order (smallest first).
    sort_order: Mapped[int] = mapped_column(Integer)
    # The filing this service is for; empty for services that are not one filing (tax audit).
    form_code: Mapped[str | None] = mapped_column(String(50))


class CaService(BaseModel):
    """One CA's price for one catalog service. Unticking a service deletes the row."""

    __tablename__ = "ca_services"
    __table_args__ = (
        UniqueConstraint("ca_profile_id", "service_id"),
        CheckConstraint("price > 0", name="positive_price"),
    )

    ca_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ca_profiles.id"), index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_catalog.id"))
    service: Mapped[CatalogService] = relationship()
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # rupees


class EngagementStatus(StrEnum):
    """Where an engagement is in its lifecycle (see the module docstring)."""

    REQUESTED = "requested"
    QUOTED = "quoted"
    ACTIVE = "active"
    COMPLETED = "completed"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Engagement(BaseModel):
    """One business working with one CA. A business may have several CAs at once.

    Never deleted: a request that ends early becomes declined, expired or cancelled.
    """

    __tablename__ = "engagements"
    __table_args__ = (
        CheckConstraint(
            "status <> 'quoted' OR quote_reason IS NOT NULL", name="quote_needs_reason"
        ),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    ca_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ca_profiles.id"), index=True)
    status: Mapped[str] = mapped_column(
        String(50), default=EngagementStatus.REQUESTED
    )
    is_pro_bono: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Why the CA's quote differs from the listed prices (required once quoted).
    quote_reason: Mapped[str | None] = mapped_column(String(1000))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # requested_at + 48 hours: an unanswered request expires then.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EngagementItem(BaseModel):
    """One filing (compliance item) in an engagement, with the service and its prices."""

    __tablename__ = "engagement_items"
    __table_args__ = (
        UniqueConstraint("engagement_id", "compliance_item_id"),
        CheckConstraint(
            "listed_price >= 0 AND (agreed_price IS NULL OR agreed_price >= 0)",
            name="prices_not_negative",
        ),
        CheckConstraint(
            "quoted_price IS NULL OR quoted_price >= 0", name="quoted_price_not_negative"
        ),
    )

    engagement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engagements.id"), index=True)
    compliance_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("compliance_items.id"), index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_catalog.id"))
    # The CA's price from their menu when requested (0 for pro bono), in rupees.
    listed_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # The CA's revised price when they send a quote; empty unless the CA quoted.
    quoted_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    # The price both sides accepted (the listed price, or the quote); empty until then.
    agreed_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class Rating(BaseModel):
    """The business's review of one engagement (at most one). Deleted normally, not soft."""

    __tablename__ = "ratings"
    __table_args__ = (CheckConstraint("stars BETWEEN 1 AND 5", name="stars_1_to_5"),)

    engagement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engagements.id"), unique=True)
    stars: Mapped[int] = mapped_column(SmallInteger)
    review: Mapped[str | None] = mapped_column(String(2000))


class ProBonoRequestStatus(StrEnum):
    """Where a business's place in the pro-bono queue stands."""

    QUEUED = "queued"
    MATCHED = "matched"
    CANCELLED = "cancelled"


class ProBonoRequest(BaseModel):
    """An eligible business waiting in the pro-bono queue; matched to one engagement."""

    __tablename__ = "pro_bono_requests"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    status: Mapped[str] = mapped_column(
        String(50), default=ProBonoRequestStatus.QUEUED
    )
    note: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    # The filings (compliance item ids) the business wants free help with.
    compliance_item_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid), default=list, server_default="{}"
    )
    # The pro-bono engagement created for it (empty while queued).
    engagement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("engagements.id"), unique=True
    )


# --- ca_workspace ------------------------------------------------------------------------


class DocumentRequestStatus(StrEnum):
    OPEN = "open"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class DocumentRequest(BaseModel):
    """A CA's request for one document, shown to the business as a to-do."""

    __tablename__ = "document_requests"

    engagement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engagements.id"), index=True)
    compliance_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compliance_items.id"))
    # The checklist entry asked for (content/forms/<FORM>/checklist.yaml), or "general".
    checklist_key: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(
        String(50), default=DocumentRequestStatus.OPEN
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The file that answered it (empty until fulfilled).
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))


# --- regulatory --------------------------------------------------------------------------


class NewsSourceKind(StrEnum):
    RSS = "rss"
    HTML = "html"


class ChangeType(StrEnum):
    DUE_DATE_EXTENSION = "due_date_extension"
    RATE_CHANGE = "rate_change"
    NEW_RULE = "new_rule"
    OTHER = "other"


class NewsSource(BaseModel):
    """A news site or official update page we scrape (switched off with `enabled`)."""

    __tablename__ = "news_sources"

    name: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(500), unique=True)
    kind: Mapped[str] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class NewsArticle(BaseModel):
    """One scraped article; `content_hash` stops the same text being stored twice."""

    __tablename__ = "news_articles"

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("news_sources.id"), index=True)
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)  # SHA-256 of content


class RegulatoryChange(BaseModel):
    """A deadline or rule change found in an article."""

    __tablename__ = "regulatory_changes"
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("news_articles.id"), index=True)
    change_type: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str] = mapped_column(Text)
    # The forms it affects, e.g. {gstr_3b}: an array of FormCode values.
    form_codes: Mapped[list[str]] = mapped_column(ARRAY(String(50)))
    # Who it affects, e.g. {"extracted_by": "ai", "gst_schemes": ["regular_monthly"],
    # "states": ["Maharashtra"]}; a missing list means everyone.
    affected_categories: Mapped[dict] = mapped_column(JSONB)
    # The dates it mentions, e.g. {"old_due_date": "2026-10-20", "new_due_date": "2026-10-31"}.
    dates: Mapped[dict] = mapped_column(JSONB)
    # When the affected users were told (empty for a change found by keywords only).
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RegulatoryChangeMatch(BaseModel):
    """A business told about a change (at most once per change)."""

    __tablename__ = "regulatory_change_matches"
    __table_args__ = (UniqueConstraint("change_id", "business_id"),)

    change_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("regulatory_changes.id"))
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --- assistant ---------------------------------------------------------------------------


EMBEDDING_SIZE = 768


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class KbChunk(BaseModel):
    """One chunk of a knowledge-base source, e.g. content/forms/GSTR-3B/explanation.md part 2."""

    __tablename__ = "kb_chunks"
    __table_args__ = (UniqueConstraint("source_path", "chunk_index"),)

    source_path: Mapped[str] = mapped_column(String(300))  # repo path or FAQ identifier
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(1000))  # the official page, for citations
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_SIZE))


class ChatMessage(BaseModel):
    """One message in a user's assistant conversation (deleted when cleared)."""

    __tablename__ = "chat_messages"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    # For an answer: {"sources": [{number, title, url, source_path, excerpt}], "ask_a_ca": bool,
    # "ai_used": bool} (assistant_service.ask). Empty for a question.
    citations: Mapped[dict | None] = mapped_column(JSONB)
