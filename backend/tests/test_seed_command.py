"""`flask seed` runs the core seeds and every module's seed() without errors."""

import pytest
from sqlalchemy import func, select

from app.core.auth.models import User
from app.core.db.enums import UserRole
from app.core.security.passwords import verify_password

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


def run_seed(app):
    result = app.test_cli_runner().invoke(args=["seed"])
    assert result.exit_code == 0, result.output
    return result


def test_seed_command_runs_core_and_all_modules(app, database, demo_env):
    result = run_seed(app)

    # Demo users always come first; modules follow once they define seed().
    assert result.output.startswith("Seeded ")
    assert "module(s): core.auth" in result.output


def test_seed_creates_one_hashed_demo_user_per_role(app, database, demo_env):
    run_seed(app)

    users = {u.role: u for u in database.session.scalars(select(User))}
    assert set(users) == set(UserRole)
    business = users[UserRole.BUSINESS]
    assert business.email == "business@demo.local"  # stored normalized
    assert business.password_hash != "business-pass"
    assert verify_password(business.password_hash, "business-pass")


def test_seed_is_idempotent(app, database, demo_env):
    run_seed(app)
    run_seed(app)

    assert database.session.scalar(select(func.count(User.id))) == 3


def test_seed_skips_roles_without_demo_variables(app, database, demo_env, monkeypatch):
    monkeypatch.delenv("DEMO_CA_PASSWORD")

    run_seed(app)

    roles = set(database.session.scalars(select(User.role)))
    assert roles == {UserRole.BUSINESS, UserRole.ADMIN}
