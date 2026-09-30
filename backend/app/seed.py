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
thresholds, the obligation templates and the penalty rules of the 7 forms are seeded too,
each with its official source; the values not confirmed yet are marked TODO_VERIFY
(docs/TODO_VERIFY.md). These three seeds also update rows seeded earlier, so a corrected
value reaches every database on the next `make seed` / `make sync`.
The official NIC activity codes are loaded from content/reference/nic_2008.csv, and the
regulatory monitor's news sources are added.

Every seed function
must be safe to re-run (it skips or updates rows that already exist) and must not commit:
run_all_seeds() commits once at the end. Add a new table's seed function to SEEDS.
"""

import csv
import logging
import os
import secrets
from datetime import date
from decimal import Decimal

import click
from flask import Flask
from sqlalchemy import select, text

from app import onboarding
from app.auth import normalize_email
from app.models import (
    CaProfile,
    CaService,
    CatalogService,
    CaVerificationStatus,
    db,
    FormCode,
    Frequency,
    NewsSource,
    NewsSourceKind,
    NicCode,
    ObligationTemplate,
    PenaltyRule,
    RuleThreshold,
    ServiceUnit,
    User,
    UserRole,
    utcnow,
)
from app.utils import hash_password, REPO_ROOT

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
    missing = []
    for code in specializations:
        if code not in profile.specializations:
            missing.append(code)
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
# Checked against official sources on 29 Sep 2026 (docs/TODO_VERIFY.md, "Verified values").
# A value whose source_reference still contains TODO_VERIFY is a proposal nobody has
# confirmed from an official text yet. When the law changes, add a row with a new
# effective_from instead of editing the old one.

RULES_FROM = date(2025, 4, 1)  # effective_from of every value below

MSME_SOURCE = (
    "Udyam Registration portal (udyamregistration.gov.in), MSME classification from "
    "1 April 2025 (MSMED Act; notification S.O. 1364(E), 21.03.2025)"
)

# (key, value, unit, description, source_reference)
RULE_THRESHOLDS = [
    (
        "msme.micro.max_investment",
        "25000000",
        "inr",
        "Micro: investment up to ₹2.5 crore",
        MSME_SOURCE,
    ),
    (
        "msme.micro.max_turnover",
        "100000000",
        "inr",
        "Micro: turnover up to ₹10 crore",
        MSME_SOURCE,
    ),
    (
        "msme.small.max_investment",
        "250000000",
        "inr",
        "Small: investment up to ₹25 crore",
        MSME_SOURCE,
    ),
    (
        "msme.small.max_turnover",
        "1000000000",
        "inr",
        "Small: turnover up to ₹100 crore",
        MSME_SOURCE,
    ),
    (
        "msme.medium.max_investment",
        "1250000000",
        "inr",
        "Medium: investment up to ₹125 crore",
        MSME_SOURCE,
    ),
    (
        "msme.medium.max_turnover",
        "5000000000",
        "inr",
        "Medium: turnover up to ₹500 crore",
        MSME_SOURCE,
    ),
    (
        "gst.registration.min_turnover",
        "2000000",
        "inr",
        "GST registration needed above ₹20 lakh (lower limit, for services)",
        "CBIC, 'GST - An Update' (1 May 2019), cbic-gst.gov.in: registration needed above "
        "₹20 lakh for services (₹10 lakh in Manipur, Mizoram, Nagaland, Tripura) and ₹40 lakh "
        "for goods (₹20 lakh in some states); CGST Act s.22, Notification 10/2019-CT",
    ),
    (
        "gst.qrmp.max_turnover",
        "50000000",
        "inr",
        "Quarterly returns (QRMP) allowed up to ₹5 crore",
        "GST portal FAQ 'Quarterly Return and Monthly Payment (QRMP) Scheme' "
        "(tutorial.gst.gov.in/userguide/returns/FAQs_change_profile.htm)",
    ),
    (
        "gst.composition.max_turnover",
        "15000000",
        "inr",
        "Composition scheme allowed up to ₹1.5 crore (goods)",
        "CBIC, 'GST - An Update' (1 May 2019): composition up to ₹1.5 crore for goods "
        "(₹75 lakh in special category states); CGST Act s.10, Notification 14/2019-CT",
    ),
    (
        "itr.presumptive_44ad.max_turnover",
        "20000000",
        "inr",
        "Presumptive scheme (44AD) allowed up to ₹2 crore",
        "incometax.gov.in, File ITR-4 (Sugam) FAQ Q9: s.44AD up to ₹2 crore (₹3 crore when "
        "cash receipts are at most 5%)",
    ),
    (
        "itr.audit_44ab.min_turnover",
        "10000000",
        "inr",
        "Tax audit needed above ₹1 crore",
        "incometax.gov.in, Income Tax Forms FAQ: tax audit above ₹1 crore for a business "
        "(₹10 crore when cash is at most 5%); s.44AB of the 1961 Act, s.63 of the 2025 Act",
    ),
]


def _upsert(model, lookup: dict, values: dict) -> None:
    """Add the row found by `lookup`, or give an existing one the current `values`."""
    stmt = select(model)
    for column, value in lookup.items():
        stmt = stmt.where(getattr(model, column) == value)
    row = db.session.scalar(stmt)
    if row is None:
        db.session.add(model(**lookup, **values))
        return
    for column, value in values.items():
        setattr(row, column, value)


def seed_rule_thresholds() -> None:
    for key, value, unit, description, source in RULE_THRESHOLDS:
        _upsert(
            RuleThreshold,
            {"key": key, "effective_from": RULES_FROM},
            {
                "value": Decimal(value),
                "unit": unit,
                "description": description,
                "source_reference": source,
            },
        )


# How each form applies and when it is due. Due-date rules (compliance_service.due_date):
#   monthly    {"day": 11}                       the 11th of the next month
#   quarterly  {"quarters": [[7, 13], ...]}      [month, day] for Q1, Q2, Q3, Q4
#   yearly     {"month": 7, "day": 31}           that date after the financial year ends
#              (ITR also has "audit_month" / "audit_day" for businesses with an audit, and
#              "by_itr_form" {"itr_5": [7, 31]}: another date without an audit for that form)
# Applicability: every key must match the regulatory profile, e.g. {"gst_scheme": [...]};
# {} means every business.
# (form, name, frequency, applicability, due_date_rule, source_reference)
GST_FAQ = "tutorial.gst.gov.in/userguide/returns/"
OBLIGATION_TEMPLATES = [
    (
        FormCode.ITR,
        "Income tax return",
        Frequency.YEARLY,
        {},
        {
            "month": 8,
            "day": 31,
            "audit_month": 10,
            "audit_day": 31,
            "by_itr_form": {"itr_5": [7, 31]},
        },
        "incometax.gov.in, Income Tax Returns FAQ Q16 and Q24: 31 August for individuals and HUFs "
        "with business or professional income and no audit (31 July only without business "
        "income: no profile of the app), 31 October with an audit; s.139(1) of the 1961 Act, "
        "s.263 of the 2025 Act as amended by Finance Act 2026. TODO_VERIFY: ITR-5 (firms, LLPs) "
        "without audit, 31 July used (sources say 31 July or 31 August; the earlier date)",
    ),
    (
        FormCode.GSTR_1,
        "GSTR-1 (monthly)",
        Frequency.MONTHLY,
        {"gst_scheme": ["regular_monthly"]},
        {"day": 11},
        f"GST portal FAQ 'Form GSTR-1' Q10 ({GST_FAQ}GSTR_1.htm): 11th of the next month",
    ),
    (
        FormCode.GSTR_1,
        "GSTR-1 (quarterly, QRMP)",
        Frequency.QUARTERLY,
        {"gst_scheme": ["regular_qrmp"]},
        {"quarters": [[7, 13], [10, 13], [1, 13], [4, 13]]},
        f"GST portal FAQ 'Form GSTR-1' Q10 ({GST_FAQ}GSTR_1.htm): 13th after the quarter",
    ),
    (
        FormCode.GSTR_3B,
        "GSTR-3B (monthly)",
        Frequency.MONTHLY,
        {"gst_scheme": ["regular_monthly"]},
        {"day": 20},
        f"GST portal FAQ 'Form GSTR-3B' ({GST_FAQ}GSTR3B.htm): 20th of the next month",
    ),
    (
        FormCode.GSTR_3B,
        "GSTR-3B (quarterly, QRMP)",
        Frequency.QUARTERLY,
        {"gst_scheme": ["regular_qrmp"]},
        {"quarters": [[7, 22], [10, 22], [1, 22], [4, 22]]},
        f"GST portal FAQ 'Form GSTR-3B' ({GST_FAQ}GSTR3B.htm) and GSTN QRMP advisory Q28: "
        "22nd or 24th after the quarter by state; the app uses the 22nd for every state "
        "(the earlier date; docs/DECISIONS.md 2026-09-29)",
    ),
    (
        FormCode.CMP_08,
        "CMP-08",
        Frequency.QUARTERLY,
        {"gst_scheme": ["composition"]},
        {"quarters": [[7, 18], [10, 18], [1, 18], [4, 18]]},
        f"GST portal FAQ 'Filing Form GST CMP-08' Q3 ({GST_FAQ}FAQs_CMP02.htm): 18th after "
        "the quarter",
    ),
    (
        FormCode.GSTR_4,
        "GSTR-4",
        Frequency.YEARLY,
        {"gst_scheme": ["composition"]},
        {"month": 6, "day": 30},
        "TODO_VERIFY: 30 June after the FY from FY 2024-25 (CGST Rules r.62 as amended by "
        "Notification 12/2024-CT, 10.07.2024; not read, the GST portal FAQ still says the "
        "30th of the month after the FY)",
    ),
    (
        FormCode.TDS_24Q,
        "TDS return 24Q (salaries)",
        Frequency.QUARTERLY,
        {"files_24q": [True]},
        {"quarters": [[7, 31], [10, 31], [1, 31], [5, 31]]},
        "incometax.gov.in, Form 138 (earlier 24Q) user manual: 31 July, 31 October, "
        "31 January, 31 May; shown as Form 138 from tax year 2026-27 (Income-tax Act 2025 "
        "s.392 and Income-tax Rules 2026; compliance_service.RENAMED_FORMS)",
    ),
    (
        FormCode.TDS_26Q,
        "TDS return 26Q (other payments)",
        Frequency.QUARTERLY,
        {"files_26q": [True]},
        {"quarters": [[7, 31], [10, 31], [1, 31], [5, 31]]},
        "incometax.gov.in, Form 140 (earlier 26Q) user manual: 31 July, 31 October, "
        "31 January, 31 May; shown as Form 140 from tax year 2026-27 (Income-tax Act 2025 "
        "s.393 and Income-tax Rules 2026; compliance_service.RENAMED_FORMS)",
    ),
]


def seed_obligation_templates() -> None:
    for form, name, frequency, applicability, rule, source in OBLIGATION_TEMPLATES:
        _upsert(
            ObligationTemplate,
            {"form_code": form, "frequency": frequency, "effective_from": RULES_FROM},
            {
                "name": name,
                "applicability": applicability,
                "due_date_rule": rule,
                "source_reference": source,
            },
        )


# One penalty rule per form: (form, amounts, source_reference). Amounts are rupees
# (annual_interest_rate is % a year); a missing amount stays empty (NULL) and the estimator
# says so. Where a fee or cap depends on turnover or income, the value for a small business
# (turnover up to ₹1.5 crore) is stored and the others are named in the source.
# docs/TODO_VERIFY.md, "Penalties", lists what each value rests on.
GST_LATE_FEE = "CBIC Circular 26/26/2017-GST: ₹50 a day (₹25 CGST + ₹25 SGST), nil ₹20"
GST_INTEREST = "TODO_VERIFY: interest 18% a year (CGST Act s.50, Notification 13/2017-CT; not read)"
PENALTY_RULES = [
    (
        FormCode.GSTR_1,
        {
            "late_fee_per_day": "50",
            "max_late_fee": "2000",
            "annual_interest_rate": "0",
        },
        "TODO_VERIFY: ₹50/₹20 a day as for GSTR-3B (Notification 4/2018-CT; not read). Cap: "
        "Notification 20/2021-CT, CGST ₹1,000 up to ₹1.5 crore (₹250 nil, ₹2,500 up to "
        "₹5 crore), doubled for SGST. No tax is paid with GSTR-1, so no interest.",
    ),
    (
        FormCode.GSTR_3B,
        {
            "late_fee_per_day": "50",
            "max_late_fee": "2000",
            "annual_interest_rate": "18",
        },
        f"{GST_LATE_FEE}. Cap: Notification 19/2021-CT, CGST ₹1,000 up to ₹1.5 crore (₹250 "
        f"nil, ₹2,500 up to ₹5 crore), doubled for SGST. {GST_INTEREST}",
    ),
    (
        FormCode.CMP_08,
        {"late_fee_per_day": "0", "max_late_fee": "0", "annual_interest_rate": "18"},
        f"GST portal FAQ 'Filing Form GST CMP-08' Q9: no late fee. {GST_INTEREST}",
    ),
    (
        FormCode.GSTR_4,
        {
            "late_fee_per_day": "50",
            "max_late_fee": "2000",
            "annual_interest_rate": "18",
        },
        "TODO_VERIFY: ₹50/₹20 a day (Notification 73/2017-CT; not read). Cap: Notification "
        f"21/2021-CT, CGST ₹1,000 (₹250 nil), doubled for SGST. {GST_INTEREST}",
    ),
    (
        FormCode.TDS_24Q,
        {"late_fee_per_day": "200", "annual_interest_rate": "0"},
        "TRACES FAQ on late filing fee (tdscpc.gov.in): ₹200 a day (s.234E), at most the TDS "
        "of the statement (not stored). A late statement has no interest (that is for late "
        "deposit).",
    ),
    (
        FormCode.TDS_26Q,
        {"late_fee_per_day": "200", "annual_interest_rate": "0"},
        "TRACES FAQ on late filing fee (tdscpc.gov.in): ₹200 a day (s.234E), at most the TDS "
        "of the statement (not stored). A late statement has no interest (that is for late "
        "deposit).",
    ),
    (
        FormCode.ITR,
        {"flat_late_fee": "5000", "annual_interest_rate": "12"},
        "incometax.gov.in, Income Tax Returns FAQ Q25: ₹5,000 (₹1,000 when income is at most "
        "₹5 lakh; s.234F, s.428 of the 2025 Act). TODO_VERIFY: interest 1% a month (s.234A; "
        "not read).",
    ),
]

PENALTY_COLUMNS = (
    "late_fee_per_day",
    "max_late_fee",
    "flat_late_fee",
    "annual_interest_rate",
)


def seed_penalty_rules() -> None:
    for form, amounts, source in PENALTY_RULES:
        values = {"source_reference": source}
        for column in PENALTY_COLUMNS:
            amount = amounts.get(column)
            values[column] = Decimal(amount) if amount is not None else None
        _upsert(PenaltyRule, {"form_code": form, "effective_from": RULES_FROM}, values)


# The official NIC activity codes (ON9): reference data, never typed by hand.
NIC_FILE = REPO_ROOT / "content" / "reference" / "nic_2008.csv"


def seed_nic_codes() -> None:
    """Add the NIC codes from content/reference/nic_2008.csv that are not in the table yet."""
    if not NIC_FILE.exists():
        log.warning("Skipping NIC codes: %s is missing", NIC_FILE)
        return

    existing = set(db.session.scalars(select(NicCode.code)))
    with open(NIC_FILE, encoding="utf-8") as handle:
        lines = []
        for line in handle:
            if not line.startswith("#"):  # the source notes at the top
                lines.append(line)
    for row in csv.DictReader(lines):
        if row["code"] not in existing:
            db.session.add(NicCode(code=row["code"], description=row["description"]))
            existing.add(row["code"])


# News sources for the regulatory monitor (RE1): (name, url, kind, enabled). Each one's
# robots.txt was checked on 2026-09-28 and allows our bot; the scanner checks it again on
# every run. The CBIC page is off until an admin switches it on (a busy home page).
NEWS_SOURCES = [
    ("TaxGuru: GST news", "https://taxguru.in/category/goods-and-service-tax/feed/", "rss", True),
    ("TaxGuru: Income tax news", "https://taxguru.in/category/income-tax/feed/", "rss", True),
    ("CBIC GST portal (home page)", "https://cbic-gst.gov.in/", "html", False),
]


def seed_news_sources() -> None:
    for name, url, kind, enabled in NEWS_SOURCES:
        if not db.session.scalar(select(NewsSource.id).where(NewsSource.url == url)):
            db.session.add(
                NewsSource(name=name, url=url, kind=NewsSourceKind(kind), enabled=enabled)
            )


def seed_filing_dates() -> None:
    """Give filings created earlier the dates of the rules seeded above (a corrected rule
    would otherwise reach a business's filings only when it edits its profile)."""
    onboarding.resync_all_filings()


# (name, function) in dependency order: users first, other data may refer to them.
SEEDS = [
    ("demo users", seed_demo_users),
    ("CA profiles", seed_ca_profiles),
    ("service catalog", seed_service_catalog),
    ("CA prices", seed_ca_prices),
    ("rule thresholds", seed_rule_thresholds),
    ("obligation templates", seed_obligation_templates),
    ("penalty rules", seed_penalty_rules),
    ("NIC codes", seed_nic_codes),
    ("news sources", seed_news_sources),
    ("filings synced to the rules", seed_filing_dates),  # last: needs the templates above
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

    @app.cli.command("seed-demo")
    def seed_demo_command() -> None:
        """Insert the fictional demo data (app/demo_seed.py) after the normal seed. Runs once."""
        from app.demo_seed import seed_demo_data  # demo_seed imports this module

        click.echo(f"Seeded: {', '.join(run_all_seeds())}")
        click.echo(seed_demo_data())

    @app.cli.command("reset-db")
    @click.confirmation_option(prompt="Delete every table and all data in DATABASE_URL?")
    def reset_db_command() -> None:
        """Drop every table, create them again from the models, then run the seed."""
        # Dropping the whole schema also removes tables that no longer have a model.
        with db.engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.create_all()
        click.echo(f"Seeded: {', '.join(run_all_seeds())}")
