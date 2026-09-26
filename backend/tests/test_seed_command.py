"""`flask seed` inserts the demo users and CA profiles, once, without errors."""

import pytest
from sqlalchemy import func, select

from app.models import CaProfile, User
from app.models.enums import UserRole
from app.models.marketplace import CaVerificationStatus
from app.seed import SAMPLE_CAS
from app.utils.passwords import verify_password

DEMO_ENV = {
    "DEMO_BUSINESS_EMAIL": " Business@Demo.local ",
    "DEMO_BUSINESS_PASSWORD": "business-pass",
    "DEMO_CA_EMAIL": "ca@demo.local",
    "DEMO_CA_PASSWORD": "ca-pass",
    "DEMO_ADMIN_EMAIL": "admin@demo.local",
    "DEMO_ADMIN_PASSWORD": "admin-pass",
}


@pytest.fixture()
def demo_env(monkeypatch):
    for name, value in DEMO_ENV.items():
        monkeypatch.setenv(name, value)


SAMPLE_EMAILS = {email for email, _, _ in SAMPLE_CAS}


def demo_users(database):
    """Seeded users except the sample CAs."""
    return [u for u in database.session.scalars(select(User)) if u.email not in SAMPLE_EMAILS]


def run_seed(app):
    result = app.test_cli_runner().invoke(args=["seed"])
    assert result.exit_code == 0, result.output
    return result


def test_seed_command_lists_what_it_seeded(app, database, demo_env):
    result = run_seed(app)

    assert "Seeded: demo users, CA profiles" in result.output


def test_seed_creates_one_hashed_demo_user_per_role(app, database, demo_env):
    run_seed(app)

    users = {u.role: u for u in demo_users(database)}
    assert set(users) == set(UserRole)
    business = users[UserRole.BUSINESS]
    assert business.email == "business@demo.local"  # stored normalized
    assert business.password_hash != "business-pass"
    assert verify_password(business.password_hash, "business-pass")
    assert all(user.email_verified_at is not None for user in users.values())  # can log in


def test_seed_is_idempotent(app, database, demo_env):
    run_seed(app)
    run_seed(app)

    assert database.session.scalar(select(func.count(User.id))) == 3 + len(SAMPLE_CAS)
    assert database.session.scalar(select(func.count(CaProfile.id))) == 1 + len(SAMPLE_CAS)


def test_seed_gives_the_demo_ca_and_sample_cas_verified_profiles(app, database, demo_env):
    run_seed(app)

    profiles = database.session.scalars(select(CaProfile)).all()
    emails = {profile.user.email for profile in profiles}
    assert emails == {"ca@demo.local"} | SAMPLE_EMAILS
    assert {p.verification_status for p in profiles} == {CaVerificationStatus.VERIFIED}


def test_seed_skips_roles_without_demo_variables(app, database, demo_env, monkeypatch):
    monkeypatch.delenv("DEMO_CA_PASSWORD")

    run_seed(app)

    roles = {user.role for user in demo_users(database)}
    assert roles == {UserRole.BUSINESS, UserRole.ADMIN}
