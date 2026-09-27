"""Development seed data and the `flask seed` command (make seed).

Demo users, one per role, come from DEMO_* variables in .env:

    DEMO_BUSINESS_EMAIL / DEMO_BUSINESS_PASSWORD
    DEMO_CA_EMAIL       / DEMO_CA_PASSWORD
    DEMO_ADMIN_EMAIL    / DEMO_ADMIN_PASSWORD

A role whose variables are empty is skipped with a warning. The demo CA gets a
verified practice profile, and four sample CAs (sample-ca-N@demo.local, random
passwords nobody knows, so they cannot log in) fill the marketplace list. The
service catalog is seeded here too (an admin editor comes later), and the four
sample CAs get prices so some typical price ranges show up. The legal rule
thresholds and the obligation templates of the 7 forms are seeded too, all marked
TODO_VERIFY until someone checks them (docs/TODO_VERIFY.md).

Every seed function
must be safe to re-run (it skips rows that already exist) and must not commit:
run_all_seeds() commits once at the end. Add a new table's seed function to SEEDS.
"""

import logging
import os
import secrets
from datetime import date
from decimal import Decimal

import click
from flask import Flask
from sqlalchemy import select

from app.extensions import db
from app.models import (
    CaProfile,
    CaService,
    CatalogService,
    ObligationTemplate,
    RuleThreshold,
    User,
)
from app.models.base import utcnow
from app.models.compliance import Frequency
from app.models.enums import FormCode, UserRole
from app.models.marketplace import (  # noqa: F401 (SERVICE_SPECIALIZATIONS: used by tests)
    SERVICE_SPECIALIZATIONS,
    CaVerificationStatus,
    ServiceUnit,
)
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
            "specializations": ["gstr_1", "gstr_3b", "cmp_08", "gstr_4", "gst_registration", "itr"],
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
            "specializations": [
                "itr",
                "accounting_bookkeeping",
                "startup_msme_advisory",
                "gstr_3b",
            ],
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
            "specializations": ["company_llp_compliance", "tax_audit", "itr", "tds_26q", "gstr_3b"],
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


def _add_missing_specializations(user_id, specializations: list) -> None:
    """Give an existing sample profile the specializations SAMPLE_CAS now lists. Does not commit.

    Sample CAs cannot log in, so nobody else edits their profiles; this keeps databases
    seeded before a specialization was added in step with SAMPLE_CAS.
    """
    profile = db.session.scalar(select(CaProfile).where(CaProfile.user_id == user_id))
    missing = [code for code in specializations if code not in profile.specializations]
    if missing:
        profile.specializations = profile.specializations + missing


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
        _add_missing_specializations(user.id, fields["specializations"])


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


# The filing each catalog service is for, so a request can find the CA's price for a
# filing. Services that are not one filing (GST registration, tax audit, ...) have none.
SERVICE_FORM_CODES = {
    "itr_presumptive": FormCode.ITR,
    "itr_business": FormCode.ITR,
    "itr_firm_company": FormCode.ITR,
    "gstr_1": FormCode.GSTR_1,
    "gstr_3b": FormCode.GSTR_3B,
    "cmp_08": FormCode.CMP_08,
    "gstr_4": FormCode.GSTR_4,
    "tds_24q": FormCode.TDS_24Q,
    "tds_26q": FormCode.TDS_26Q,
}


def seed_service_catalog() -> None:
    sort_order = 1
    for code, name, description, unit in SERVICE_CATALOG:
        service = db.session.scalar(select(CatalogService).where(CatalogService.code == code))
        if service is None:
            service = CatalogService(
                code=code, name=name, description=description, unit=unit, sort_order=sort_order
            )
            db.session.add(service)
        # Set every time: databases seeded before this column existed get it too.
        service.form_code = SERVICE_FORM_CODES.get(code)
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


# --- Legal values (CLAUDE.md rule 3) ----------------------------------------------
# NOT VERIFIED YET. Every value below is marked TODO_VERIFY and listed in
# docs/TODO_VERIFY.md. When someone checks a value against the official source,
# they update its row here (value + source) and in that file.

RULES_FROM = date(2025, 4, 1)  # effective_from of every value below

# (key, value, unit, description, source_reference)
RULE_THRESHOLDS = [
    (
        "msme.micro.max_investment",
        "25000000",
        "inr",
        "Micro: investment up to ₹2.5 crore",
        "TODO_VERIFY: MSME classification limits, Ministry of MSME",
    ),
    (
        "msme.micro.max_turnover",
        "100000000",
        "inr",
        "Micro: turnover up to ₹10 crore",
        "TODO_VERIFY: MSME classification limits, Ministry of MSME",
    ),
    (
        "msme.small.max_investment",
        "250000000",
        "inr",
        "Small: investment up to ₹25 crore",
        "TODO_VERIFY: MSME classification limits, Ministry of MSME",
    ),
    (
        "msme.small.max_turnover",
        "1000000000",
        "inr",
        "Small: turnover up to ₹100 crore",
        "TODO_VERIFY: MSME classification limits, Ministry of MSME",
    ),
    (
        "msme.medium.max_investment",
        "1250000000",
        "inr",
        "Medium: investment up to ₹125 crore",
        "TODO_VERIFY: MSME classification limits, Ministry of MSME",
    ),
    (
        "msme.medium.max_turnover",
        "5000000000",
        "inr",
        "Medium: turnover up to ₹500 crore",
        "TODO_VERIFY: MSME classification limits, Ministry of MSME",
    ),
    (
        "gst.registration.min_turnover",
        "2000000",
        "inr",
        "GST registration needed above ₹20 lakh (lower limit, for services)",
        "TODO_VERIFY: CGST Act section 22 and notifications",
    ),
    (
        "gst.qrmp.max_turnover",
        "50000000",
        "inr",
        "Quarterly returns (QRMP) allowed up to ₹5 crore",
        "TODO_VERIFY: QRMP scheme, CBIC",
    ),
    (
        "gst.composition.max_turnover",
        "15000000",
        "inr",
        "Composition scheme allowed up to ₹1.5 crore (goods)",
        "TODO_VERIFY: CGST Act section 10 and notifications",
    ),
    (
        "itr.presumptive_44ad.max_turnover",
        "20000000",
        "inr",
        "Presumptive scheme (44AD) allowed up to ₹2 crore",
        "TODO_VERIFY: Income-tax Act section 44AD",
    ),
    (
        "itr.audit_44ab.min_turnover",
        "10000000",
        "inr",
        "Tax audit needed above ₹1 crore",
        "TODO_VERIFY: Income-tax Act section 44AB",
    ),
]


def seed_rule_thresholds() -> None:
    for key, value, unit, description, source in RULE_THRESHOLDS:
        exists = db.session.scalar(
            select(RuleThreshold.id).where(
                RuleThreshold.key == key, RuleThreshold.effective_from == RULES_FROM
            )
        )
        if not exists:
            db.session.add(
                RuleThreshold(
                    key=key,
                    value=Decimal(value),
                    unit=unit,
                    description=description,
                    source_reference=source,
                    effective_from=RULES_FROM,
                )
            )


# How each form applies and when it is due. Due-date rules (compliance_service.due_date):
#   monthly    {"day": 11}                       the 11th of the next month
#   quarterly  {"quarters": [[7, 13], ...]}      [month, day] for Q1, Q2, Q3, Q4
#   yearly     {"month": 7, "day": 31}           that date after the financial year ends
#              (ITR also has "audit_month" / "audit_day" for businesses with a tax audit)
# Applicability: every key must match the regulatory profile, e.g. {"gst_scheme": [...]};
# {} means every business.
# (form, name, frequency, applicability, due_date_rule, source_reference)
OBLIGATION_TEMPLATES = [
    (
        FormCode.ITR,
        "Income tax return",
        Frequency.YEARLY,
        {},
        {"month": 7, "day": 31, "audit_month": 10, "audit_day": 31},
        "TODO_VERIFY: Income-tax Act section 139(1)",
    ),
    (
        FormCode.GSTR_1,
        "GSTR-1 (monthly)",
        Frequency.MONTHLY,
        {"gst_scheme": ["regular_monthly"]},
        {"day": 11},
        "TODO_VERIFY: CGST Rules rule 59",
    ),
    (
        FormCode.GSTR_1,
        "GSTR-1 (quarterly, QRMP)",
        Frequency.QUARTERLY,
        {"gst_scheme": ["regular_qrmp"]},
        {"quarters": [[7, 13], [10, 13], [1, 13], [4, 13]]},
        "TODO_VERIFY: CGST Rules rule 59, QRMP",
    ),
    (
        FormCode.GSTR_3B,
        "GSTR-3B (monthly)",
        Frequency.MONTHLY,
        {"gst_scheme": ["regular_monthly"]},
        {"day": 20},
        "TODO_VERIFY: CGST Rules rule 61",
    ),
    (
        FormCode.GSTR_3B,
        "GSTR-3B (quarterly, QRMP)",
        Frequency.QUARTERLY,
        {"gst_scheme": ["regular_qrmp"]},
        {"quarters": [[7, 22], [10, 22], [1, 22], [4, 22]]},
        "TODO_VERIFY: CGST Rules rule 61, QRMP (22nd or 24th by state)",
    ),
    (
        FormCode.CMP_08,
        "CMP-08",
        Frequency.QUARTERLY,
        {"gst_scheme": ["composition"]},
        {"quarters": [[7, 18], [10, 18], [1, 18], [4, 18]]},
        "TODO_VERIFY: CGST Rules rule 62",
    ),
    (
        FormCode.GSTR_4,
        "GSTR-4",
        Frequency.YEARLY,
        {"gst_scheme": ["composition"]},
        {"month": 4, "day": 30},
        "TODO_VERIFY: CGST Rules rule 62",
    ),
    (
        FormCode.TDS_24Q,
        "TDS return 24Q (salaries)",
        Frequency.QUARTERLY,
        {"files_24q": [True]},
        {"quarters": [[7, 31], [10, 31], [1, 31], [5, 31]]},
        "TODO_VERIFY: Income-tax Rules rule 31A",
    ),
    (
        FormCode.TDS_26Q,
        "TDS return 26Q (other payments)",
        Frequency.QUARTERLY,
        {"files_26q": [True]},
        {"quarters": [[7, 31], [10, 31], [1, 31], [5, 31]]},
        "TODO_VERIFY: Income-tax Rules rule 31A",
    ),
]


def seed_obligation_templates() -> None:
    for form, name, frequency, applicability, rule, source in OBLIGATION_TEMPLATES:
        exists = db.session.scalar(
            select(ObligationTemplate.id).where(
                ObligationTemplate.form_code == form,
                ObligationTemplate.frequency == frequency,
                ObligationTemplate.effective_from == RULES_FROM,
            )
        )
        if not exists:
            db.session.add(
                ObligationTemplate(
                    form_code=form,
                    name=name,
                    frequency=frequency,
                    applicability=applicability,
                    due_date_rule=rule,
                    source_reference=source,
                    effective_from=RULES_FROM,
                )
            )


# (name, function) in dependency order: users first, other data may refer to them.
SEEDS = [
    ("demo users", seed_demo_users),
    ("CA profiles", seed_ca_profiles),
    ("service catalog", seed_service_catalog),
    ("CA prices", seed_ca_prices),
    ("rule thresholds", seed_rule_thresholds),
    ("obligation templates", seed_obligation_templates),
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
