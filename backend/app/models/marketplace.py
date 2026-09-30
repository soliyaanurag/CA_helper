"""Marketplace tables: CA profiles, the service catalog, CA prices, and the work between
businesses and CAs.

    ca_profiles        a CA's practice profile (CaProfile)
    service_catalog    the standard services every CA prices against (CatalogService)
    ca_services        one CA's price for one catalog service (CaService)
    engagements        one business working with one CA (Engagement)
    engagement_items   the filings an engagement covers, with their prices (EngagementItem)
    ratings            the business's review of a finished engagement (Rating)
    client_invites     a CA's invitation to an existing client (ClientInvite)
    pro_bono_requests  a business waiting for a pro-bono CA (ProBonoRequest)

`ca_profiles`: a CA's practice profile, shown to businesses once verified.

A CA fills it in after signup (membership number, Certificate of Practice number,
city, languages, specializations, capacity). An admin checks the numbers and sets
`verification_status`; only `verified` profiles appear in the marketplace.

`languages` and `specializations` are Postgres arrays of codes, e.g.
{itr,gstr_1,tax_audit}. A CHECK constraint accepts only the codes listed below, and
"CAs who do ITR" is `specializations @> ARRAY['itr']` (GIN index). Labels for the
codes: frontend/src/lib/labels.js and docs/DATA_MODEL.md.

`service_catalog` is a fixed list (seeded; an admin editor comes later), so every
CA's price for "GSTR-3B filing" means the same thing and prices can be compared.
The typical price range is not stored: marketplace_service works it out from
`ca_services` each time.

Engagement lifecycle (EngagementStatus): requested -> active (the CA accepts the listed
prices) | requested -> quoted -> active (the business accepts the CA's quote) | declined |
expired (48 hours without an answer) | cancelled (by the business); active -> completed.
Service rule, not enforceable here: a compliance item is in at most ONE open engagement
(requested, quoted or active).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, utcnow
from app.models.enums import FormCode, only_codes, str_enum
from app.models.user import User


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
        only_codes("specializations", CA_SPECIALIZATIONS),
        only_codes("languages", CA_LANGUAGES),
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
    verification_status: Mapped[CaVerificationStatus] = mapped_column(
        str_enum(CaVerificationStatus), default=CaVerificationStatus.PENDING
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
    unit: Mapped[ServiceUnit] = mapped_column(str_enum(ServiceUnit))
    # Services are listed in this order (smallest first).
    sort_order: Mapped[int] = mapped_column(Integer)
    # The filing this service is for; empty for services that are not one filing (tax audit).
    form_code: Mapped[FormCode | None] = mapped_column(str_enum(FormCode))


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
    status: Mapped[EngagementStatus] = mapped_column(
        str_enum(EngagementStatus), default=EngagementStatus.REQUESTED
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


class InviteStatus(StrEnum):
    """Where a CA's invitation to an existing client stands."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ClientInvite(BaseModel):
    """A CA's email invitation to an existing client, who must approve the CA's access."""

    __tablename__ = "client_invites"

    ca_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ca_profiles.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), index=True)  # normalized, like users.email
    # SHA-256 of the one-time token in the invitation link; the token itself is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[InviteStatus] = mapped_column(
        str_enum(InviteStatus), default=InviteStatus.PENDING
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # The business that accepted (empty until then).
    accepted_business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id"))


class ProBonoRequestStatus(StrEnum):
    """Where a business's place in the pro-bono queue stands."""

    QUEUED = "queued"
    MATCHED = "matched"
    CANCELLED = "cancelled"


class ProBonoRequest(BaseModel):
    """An eligible business waiting in the pro-bono queue; matched to one engagement."""

    __tablename__ = "pro_bono_requests"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    status: Mapped[ProBonoRequestStatus] = mapped_column(
        str_enum(ProBonoRequestStatus), default=ProBonoRequestStatus.QUEUED
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
