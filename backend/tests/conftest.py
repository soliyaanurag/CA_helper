"""Shared pytest fixtures for all backend tests (pytest loads this file automatically).

Fixtures:
    app       Flask app built with TestingConfig (one per test session)
    client    Flask test client for calling the API
    database  test database with every table created (once per session). Every
              row is deleted after each test, so tests never see each other's
              data. Request it in any test that touches the DB.
    make_user    factory: make_user(role=UserRole.CA, is_active=False) -> User (needs `database`);
                 the user's email is verified unless you pass email_verified_at=None
    auth_headers auth_headers(user) -> {"Authorization": "Bearer <access token>"}
    mailbox      emails "sent" during the test (list of EmailMessage); emptied before each test

Rate-limit counters are cleared before every test (autouse), so login tests
never hit the limit because of earlier tests.

The test database (TEST_DATABASE_URL, default `ca_helper_test`) is created
automatically if it does not exist. It needs `make infra` to be running.
"""

import re

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app import create_app
from app.extensions import db as _db
from app.extensions import limiter
from app.models import User
from app.models.base import utcnow
from app.models.enums import UserRole
from app.services.auth_service import issue_access_token
from app.utils.email import outbox
from app.utils.passwords import hash_password

TEST_PASSWORD = "Correct-Horse-9"


def emailed_code(message) -> str:
    """The 6-digit code in an email sent by auth_service."""
    return re.search(r"\b([0-9]{6})\b", message.get_content()).group(1)


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    with app.app_context():
        yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def _create_database_if_missing(url: str) -> None:
    """Connect to the server's `postgres` database and CREATE the test database if needed."""
    target = make_url(url)
    engine = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def _schema(app):
    url = app.config["SQLALCHEMY_DATABASE_URI"]
    if not url:
        pytest.fail("TEST_DATABASE_URL is not set. Copy it from .env.example into .env.")
    try:
        _create_database_if_missing(url)
    except OperationalError as exc:
        safe_url = make_url(url).render_as_string(hide_password=True)
        pytest.fail(
            f"Cannot reach the test database at {safe_url}. Is `make infra` running?\n{exc}"
        )

    _db.create_all()
    yield _db
    _db.session.remove()
    _db.drop_all()


@pytest.fixture()
def database(_schema):
    yield _schema
    # Services really commit, so empty every table after the test. Children go
    # before parents (reverse foreign-key order), so no foreign key blocks a delete.
    _schema.session.rollback()  # drop anything the test left uncommitted
    for table in reversed(_schema.metadata.sorted_tables):
        _schema.session.execute(table.delete())
    _schema.session.commit()


@pytest.fixture(autouse=True)
def _reset_rate_limits(app):
    limiter.reset()


@pytest.fixture(autouse=True)
def mailbox():
    """TestingConfig suppresses sending; app.utils.email.outbox collects the messages."""
    outbox.clear()
    return outbox


@pytest.fixture()
def make_user(database):
    """Create and commit a user; the password is always TEST_PASSWORD."""
    counter = iter(range(1, 10_000))

    def _make_user(
        role: UserRole = UserRole.BUSINESS,
        email: str | None = None,
        full_name: str = "Test User",
        **fields,
    ) -> User:
        fields.setdefault("password_hash", hash_password(TEST_PASSWORD))
        fields.setdefault("email_verified_at", utcnow())
        user = User(
            email=email or f"user{next(counter)}@example.com",
            full_name=full_name,
            role=role,
            **fields,
        )
        database.session.add(user)
        database.session.commit()
        return user

    return _make_user


@pytest.fixture()
def auth_headers(app):
    """Build an Authorization header with a real access token for a user."""

    def _auth_headers(user: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {issue_access_token(user)}"}

    return _auth_headers
