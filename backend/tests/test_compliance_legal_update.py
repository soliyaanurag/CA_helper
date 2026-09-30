"""The 2026 legal update: TDS returns shown as Form 138 / Form 140 from tax year 2026-27, the
ITR due date by form, and filings created earlier moved to the current rules (flask seed)."""

from datetime import date

import pytest

from app import (
    alerts as alerts_service,
    compliance as compliance_service,
    onboarding as onboarding_service,
)
from app.models import (
    Business,
    ComplianceItem,
    ComplianceStatus,
    EntityType,
    FormCode,
    ObligationTemplate,
    RegulatoryProfile,
    User,
    UserRole,
    utcnow,
)
from app.seed import run_all_seeds

TODAY = date(2026, 9, 28)


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    for module in (compliance_service, onboarding_service):
        monkeypatch.setattr(module, "today_in_india", lambda: TODAY)


def make_business(database, make_user, entity, turnover=4_500_000, **fields) -> Business:
    """A registered business with its profile and this year's filings (as registration does)."""
    user = make_user(role=UserRole.BUSINESS)
    business = Business(
        user_id=user.id,
        legal_name="Demo Co",
        entity_type=entity,
        state="Maharashtra",
        address="Pune",
        description="Shop",
        annual_turnover=turnover,
        investment_amount=500_000,
        pan="ABCFE1234F",
        phone="9000000000",
        gst_registered=False,
        cin_llpin="AAB-1234" if entity in (EntityType.LLP, EntityType.PRIVATE_LIMITED) else None,
        tan="PNEA12345B" if fields.get("deducts_tds") else None,
        deducts_tds=fields.pop("deducts_tds", False),
        pays_salary_above_limit=fields.pop("pays_salary_above_limit", False),
        **fields,
    )
    database.session.add(business)
    database.session.flush()
    profile = RegulatoryProfile(
        business_id=business.id,
        computed_at=utcnow(),
        **onboarding_service.compute_profile(business, TODAY),
    )
    database.session.add(profile)
    compliance_service.create_filings(business.id, profile, TODAY)
    database.session.commit()
    return business


def itr_of(database, business) -> ComplianceItem:
    return (
        database.session.query(ComplianceItem)
        .filter_by(business_id=business.id, form_code="itr")
        .one()
    )


# --- Display names (Form 138 / Form 140) --------------------------------------------------


def test_tds_forms_have_their_new_names_from_tax_year_2026_27():
    assert compliance_service.form_name(FormCode.TDS_24Q, "2026-27") == "Form 138 (earlier 24Q)"
    assert compliance_service.form_name(FormCode.TDS_26Q, "2027-28") == "Form 140 (earlier 26Q)"
    assert compliance_service.form_name(FormCode.TDS_24Q, "2025-26") == "24Q"
    assert compliance_service.form_name(FormCode.TDS_26Q, "2025-26") == "26Q"
    assert compliance_service.form_name(FormCode.GSTR_3B, "2026-27") == "GSTR-3B"


def test_a_tds_filing_page_and_reminder_use_the_new_name(
    client, database, make_user, auth_headers, legal_rules
):
    business = make_business(
        database,
        make_user,
        EntityType.PRIVATE_LIMITED,
        deducts_tds=True,
        pays_salary_above_limit=True,
    )
    q2 = (
        database.session.query(ComplianceItem)
        .filter_by(business_id=business.id, form_code="tds_24q", period_label="Q2 2026-27")
        .one()
    )
    owner = database.session.get(User, business.user_id)

    page = client.get(f"/api/v1/compliance/items/{q2.id}", headers=auth_headers(owner)).get_json()

    assert q2.form_code == FormCode.TDS_24Q  # the code stays
    assert page["form_name"] == "TDS return, salary (Form 138, earlier 24Q)"
    assert compliance_service.filing_name(q2) == "Form 138 (earlier 24Q) (Q2 2026-27)"
    assert (
        alerts_service._reminder_title(q2, 7)
        == "Form 138 (earlier 24Q) (Q2 2026-27) is due in 7 days"
    )


# --- ITR due date by form ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("entity", "fields", "due"),
    [
        (EntityType.PROPRIETORSHIP, {}, date(2027, 8, 31)),  # ITR-4 (presumptive), no audit
        (EntityType.INDIVIDUAL, {}, date(2027, 8, 31)),  # freelancer: professional income
        (EntityType.LLP, {}, date(2027, 7, 31)),  # ITR-5 without audit (TODO_VERIFY)
        (EntityType.PRIVATE_LIMITED, {}, date(2027, 10, 31)),  # accounts audited (company law)
        (EntityType.PROPRIETORSHIP, {"turnover": 250_000_000}, date(2027, 10, 31)),  # tax audit
    ],
)
def test_itr_due_date_follows_the_profile(database, make_user, legal_rules, entity, fields, due):
    business = make_business(database, make_user, entity, **fields)

    assert itr_of(database, business).due_date == due


# --- Filings created earlier get the current rules ----------------------------------------


def test_seed_moves_not_started_filings_to_the_current_rule(database, make_user, legal_rules):
    llp = make_business(database, make_user, EntityType.LLP, deducts_tds=True)
    itr = itr_of(database, llp)
    # As if the filing was made under an older rule (31 August for every non-audit case).
    itr.due_date = date(2027, 8, 31)
    filed = (
        database.session.query(ComplianceItem)
        .filter_by(business_id=llp.id, form_code="tds_26q", period_label="Q1 2026-27")
        .one()
    )
    filed.status = ComplianceStatus.FILED
    filed.due_date = date(2026, 1, 1)  # a filed filing keeps its date, whatever the rule says
    database.session.commit()

    run_all_seeds()

    database.session.expire_all()
    assert itr_of(database, llp).due_date == date(2027, 7, 31)
    assert database.session.get(ComplianceItem, filed.id).due_date == date(2026, 1, 1)


def test_resync_moves_the_due_date_back_to_the_rule(database, make_user, legal_rules):
    llp = make_business(database, make_user, EntityType.LLP)
    itr_of(database, llp).due_date = date(2027, 8, 31)
    database.session.commit()

    counts = onboarding_service.resync_all_filings(TODAY)

    assert counts["businesses"] == 1
    assert itr_of(database, llp).due_date == date(2027, 7, 31)
    assert counts["added"] == counts["removed"] == 0


def test_the_seed_lists_the_resync(app, database, legal_rules):
    result = app.test_cli_runner().invoke(args=["seed"])

    assert "filings synced to the rules" in result.output
    assert database.session.query(ObligationTemplate).filter_by(form_code="itr").count() == 1
