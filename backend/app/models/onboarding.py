"""Onboarding tables: businesses, their computed regulatory profile, and reference data.

    businesses           one registered business per business user (Business)
    regulatory_profiles  the current computed profile of a business, 1-1 (RegulatoryProfile)
    nic_codes            the official NIC activity codes (NicCode)
    rule_thresholds      legal thresholds and values, versioned by dates (RuleThreshold)

PAN, GSTIN, TAN and phone are encrypted (EncryptedString, CLAUDE.md rule 4): they cannot
be searched or made unique. Service rule: only a user with role `business` owns a business.
Legal values live in rule_thresholds with a source (rule 3); never invent one.
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.utils.encryption import EncryptedString


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
