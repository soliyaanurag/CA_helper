"""Marketplace tables: CA profiles, the service catalog and each CA's prices.

    ca_profiles      a CA's practice profile (CaProfile)
    service_catalog  the standard services every CA prices against (CatalogService)
    ca_services      one CA's price for one catalog service (CaService)

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
"""

import uuid
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, SoftDeleteMixin
from app.models.enums import str_enum
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


def _only_codes(column: str, codes: tuple[str, ...]) -> CheckConstraint:
    """CHECK that every item of an array column is one of `codes` (`<@` = "is contained in")."""
    allowed = ", ".join(f"'{code}'" for code in codes)
    return CheckConstraint(f"{column} <@ ARRAY[{allowed}]::varchar[]", name=f"known_{column}")


class CaProfile(SoftDeleteMixin, BaseModel):
    """One CA's practice profile (at most one per CA user)."""

    __tablename__ = "ca_profiles"
    __table_args__ = (
        _only_codes("specializations", CA_SPECIALIZATIONS),
        _only_codes("languages", CA_LANGUAGES),
        Index("ix_ca_profiles_specializations", "specializations", postgresql_using="gin"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    user: Mapped[User] = relationship()
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


class ServiceUnit(StrEnum):
    """What one price of a catalog service pays for."""

    PER_RETURN = "per_return"
    PER_MONTH = "per_month"
    PER_YEAR = "per_year"
    ONE_TIME = "one_time"
    PER_NOTICE = "per_notice"


class CatalogService(SoftDeleteMixin, BaseModel):
    """One standard service, e.g. "GSTR-3B filing", priced per return."""

    __tablename__ = "service_catalog"

    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(300))
    unit: Mapped[ServiceUnit] = mapped_column(str_enum(ServiceUnit))
    # Services are listed in this order (smallest first).
    sort_order: Mapped[int] = mapped_column(Integer)


class CaService(SoftDeleteMixin, BaseModel):
    """One CA's price for one catalog service. Unticking a service soft-deletes the row."""

    __tablename__ = "ca_services"
    __table_args__ = (
        UniqueConstraint("ca_profile_id", "service_id"),
        CheckConstraint("price > 0", name="positive_price"),
    )

    ca_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ca_profiles.id"), index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_catalog.id"))
    service: Mapped[CatalogService] = relationship()
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # rupees
