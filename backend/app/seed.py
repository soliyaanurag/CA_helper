"""Development seed data and the `flask seed` command (make seed).

Demo users, one per role, come from DEMO_* variables in .env:

    DEMO_BUSINESS_EMAIL / DEMO_BUSINESS_PASSWORD
    DEMO_CA_EMAIL       / DEMO_CA_PASSWORD
    DEMO_ADMIN_EMAIL    / DEMO_ADMIN_PASSWORD

A role whose variables are empty is skipped with a warning. The demo CA gets a
verified practice profile, and four sample CAs (sample-ca-N@demo.local, random
passwords nobody knows, so they cannot log in) fill the marketplace list. The
service catalog is seeded here too (an admin editor comes later), and the four
sample CAs get prices so some typical price ranges show up.

Every seed function
must be safe to re-run (it skips rows that already exist) and must not commit:
run_all_seeds() commits once at the end. Add a new table's seed function to SEEDS.
"""

import logging
import os
import secrets
from decimal import Decimal

import click
from flask import Flask
from sqlalchemy import select

from app.extensions import db
from app.models import CaProfile, CaService, CatalogService, User
from app.models.base import utcnow
from app.models.enums import UserRole
from app.models.marketplace import CaVerificationStatus, ServiceUnit
from app.services.auth_service import normalize_email
from app.utils.passwords import hash_password

log = logging.getLogger(__name__)

DEMO_NAMES = {
    UserRole.BUSINESS: "Demo Business Owner",
    UserRole.CA: "Demo CA",
    UserRole.ADMIN: "Demo Admin",
}


def seed_demo_users() -> None:
    for role, full_name in DEMO_NAMES.items():
        prefix = f"DEMO_{role.value.upper()}"
        email = normalize_email(os.getenv(f"{prefix}_EMAIL", ""))
        password = os.getenv(f"{prefix}_PASSWORD", "")
        if not email or not password:
            log.warning("Skipping demo %s user: set %s_EMAIL and %s_PASSWORD", role, prefix, prefix)
            continue
        if db.session.scalar(select(User.id).where(User.email == email)):
            continue
        db.session.add(
            User(
                email=email,
                password_hash=hash_password(password),
                full_name=full_name,
                role=role,
                email_verified_at=utcnow(),  # demo users can log in without a code
            )
        )
        log.info("Added demo %s user", role)


# Made-up practices for development. The membership numbers are fictional.
DEMO_CA_PROFILE = {
    "membership_no": "900000",
    "cop_number": "COP-900000",
    "city": "Mumbai",
    "languages": ["english", "hindi", "marathi"],
    "specializations": ["itr", "gstr_1", "gstr_3b", "tax_audit"],
    "capacity": 25,
    "years_experience": 8,
    "about": "Demo practice for small traders and freelancers in Mumbai.",
}

# (email, full name, profile fields)
SAMPLE_CAS = [
    (
        "sample-ca-1@demo.local",
        "Priya Iyer",
        {
            "membership_no": "900001",
            "cop_number": "COP-900001",
            "city": "Chennai",
            "languages": ["english", "tamil"],
            "specializations": ["itr", "tds_24q", "tds_26q", "income_tax_notices"],
            "capacity": 30,
            "years_experience": 12,
            "about": "Income tax and TDS for salaried professionals and small employers.",
        },
    ),
    (
        "sample-ca-2@demo.local",
        "Rahul Mehta",
        {
            "membership_no": "900002",
            "cop_number": "COP-900002",
            "city": "Ahmedabad",
            "languages": ["english", "hindi", "gujarati"],
            "specializations": ["gstr_1", "gstr_3b", "cmp_08", "gstr_4", "gst_registration"],
            "capacity": 40,
            "years_experience": 6,
            "about": "GST for traders: registration, monthly and composition returns.",
        },
    ),
    (
        "sample-ca-3@demo.local",
        "Ananya Sen",
        {
            "membership_no": "900003",
            "cop_number": "COP-900003",
            "city": "Kolkata",
            "languages": ["english", "bengali", "hindi"],
            "specializations": ["itr", "accounting_bookkeeping", "startup_msme_advisory"],
            "capacity": 15,
            "years_experience": 3,
            "about": "Bookkeeping and ITR for first-time founders and gig workers.",
        },
    ),
    (
        "sample-ca-4@demo.local",
        "Vikram Rao",
        {
            "membership_no": "900004",
            "cop_number": "COP-900004",
            "city": "Bengaluru",
            "languages": ["english", "kannada", "telugu"],
            "specializations": ["company_llp_compliance", "tax_audit", "itr", "tds_26q"],
            "capacity": 20,
            "years_experience": 15,
            "about": "Audits and compliance for LLPs and private limited companies.",
        },
    ),
]


def _add_verified_profile(user_id, fields: dict) -> None:
    """Add a verified CA profile unless the user already has one. Does not commit."""
    if db.session.scalar(select(CaProfile.id).where(CaProfile.user_id == user_id)):
        return
    db.session.add(
        CaProfile(user_id=user_id, verification_status=CaVerificationStatus.VERIFIED, **fields)
    )


def seed_ca_profiles() -> None:
    demo_email = normalize_email(os.getenv("DEMO_CA_EMAIL", ""))
    demo_ca_id = db.session.scalar(select(User.id).where(User.email == demo_email))
    if demo_email and demo_ca_id:
        _add_verified_profile(demo_ca_id, DEMO_CA_PROFILE)

    for email, full_name, fields in SAMPLE_CAS:
        user = db.session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(32)),  # nobody knows it
                full_name=full_name,
                role=UserRole.CA,
                email_verified_at=utcnow(),
            )
            db.session.add(user)
            db.session.flush()  # gives user.id
        _add_verified_profile(user.id, fields)


# The standard services every CA prices against: (code, name, description, unit).
# Listed in this order.
SERVICE_CATALOG = [
    (
        "itr_presumptive",
        "ITR filing: presumptive income (ITR-4)",
        "Income tax return for a business or profession on presumptive income.",
        ServiceUnit.PER_RETURN,
    ),
    (
        "itr_business",
        "ITR filing: business or profession (ITR-3)",
        "Income tax return for a proprietor or professional with business income.",
        ServiceUnit.PER_RETURN,
    ),
    (
        "itr_firm_company",
        "ITR filing: firm, LLP or company (ITR-5 / ITR-6)",
        "Income tax return for a partnership firm, LLP or company.",
        ServiceUnit.PER_RETURN,
    ),
    ("gstr_1", "GSTR-1 filing", "Return of outward supplies (sales).", ServiceUnit.PER_RETURN),
    ("gstr_3b", "GSTR-3B filing", "Summary GST return with tax payment.", ServiceUnit.PER_RETURN),
    (
        "cmp_08",
        "CMP-08 filing",
        "Statement for composition-scheme taxpayers.",
        ServiceUnit.PER_RETURN,
    ),
    (
        "gstr_4",
        "GSTR-4 filing",
        "Annual return for composition-scheme taxpayers.",
        ServiceUnit.PER_RETURN,
    ),
    (
        "tds_24q",
        "TDS return 24Q",
        "TDS return for tax deducted on salaries.",
        ServiceUnit.PER_RETURN,
    ),
    (
        "tds_26q",
        "TDS return 26Q",
        "TDS return for tax deducted on other payments.",
        ServiceUnit.PER_RETURN,
    ),
    (
        "gst_registration",
        "GST registration",
        "Getting a new GST registration.",
        ServiceUnit.ONE_TIME,
    ),
    (
        "tax_audit",
        "Tax audit",
        "Tax audit of the accounts for one financial year.",
        ServiceUnit.PER_YEAR,
    ),
    (
        "bookkeeping",
        "Bookkeeping",
        "Keeping the books of accounts up to date.",
        ServiceUnit.PER_MONTH,
    ),
    (
        "income_tax_notice",
        "Reply to an income-tax notice",
        "Reading an income-tax notice and preparing the reply.",
        ServiceUnit.PER_NOTICE,
    ),
]

# Sample prices (rupees) of the sample CAs, by email and service code. Made up for
# development, so some typical price ranges have data. The demo CA gets no prices:
# set them yourself on /ca/services.
SAMPLE_PRICES = {
    "sample-ca-1@demo.local": {
        "itr_presumptive": "1200",
        "itr_business": "2500",
        "tds_24q": "1500",
        "tds_26q": "1500",
        "income_tax_notice": "3000",
    },
    "sample-ca-2@demo.local": {
        "itr_presumptive": "900",
        "gstr_1": "500",
        "gstr_3b": "600",
        "cmp_08": "800",
        "gstr_4": "2000",
        "gst_registration": "1500",
    },
    "sample-ca-3@demo.local": {
        "itr_presumptive": "1000",
        "itr_business": "2000",
        "gstr_3b": "700",
        "bookkeeping": "2500",
    },
    "sample-ca-4@demo.local": {
        "itr_business": "4000",
        "itr_firm_company": "8000",
        "gstr_3b": "1000",
        "tax_audit": "30000",
        "tds_26q": "2000",
    },
}


def seed_service_catalog() -> None:
    sort_order = 1
    for code, name, description, unit in SERVICE_CATALOG:
        exists = db.session.scalar(select(CatalogService.id).where(CatalogService.code == code))
        if not exists:
            db.session.add(
                CatalogService(
                    code=code, name=name, description=description, unit=unit, sort_order=sort_order
                )
            )
        sort_order = sort_order + 1


def seed_ca_prices() -> None:
    for email, prices in SAMPLE_PRICES.items():
        profile = db.session.scalar(
            select(CaProfile).join(CaProfile.user).where(User.email == email)
        )
        if profile is None:
            continue
        for code, price in prices.items():
            service = db.session.scalar(select(CatalogService).where(CatalogService.code == code))
            exists = db.session.scalar(
                select(CaService.id).where(
                    CaService.ca_profile_id == profile.id, CaService.service_id == service.id
                )
            )
            if not exists:
                db.session.add(
                    CaService(ca_profile_id=profile.id, service_id=service.id, price=Decimal(price))
                )


# (name, function) in dependency order: users first, other data may refer to them.
SEEDS = [
    ("demo users", seed_demo_users),
    ("CA profiles", seed_ca_profiles),
    ("service catalog", seed_service_catalog),
    ("CA prices", seed_ca_prices),
]


def run_all_seeds() -> list[str]:
    """Run every seed function, then commit once. Returns the names that ran."""
    for _, seed in SEEDS:
        seed()
    db.session.commit()
    return [name for name, _ in SEEDS]


def register_commands(app: Flask) -> None:
    @app.cli.command("seed")
    def seed_command() -> None:
        """Insert development seed data. Safe to re-run."""
        click.echo(f"Seeded: {', '.join(run_all_seeds())}")
