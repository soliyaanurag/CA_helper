"""Shared pytest fixtures for ALL backend tests.

This file sits in backend/ (not backend/tests/) on purpose: pytest applies a
conftest.py only to its own folder and below, and tests live both in
backend/tests/ and in app/modules/<module>/tests/.

Fixtures:
    app       Flask app built with TestingConfig (one per test session)
    client    Flask test client for calling the API
    database  the test database with every table created; after the test all rows
              are deleted. Request it in any test that touches the DB.
    make_user    factory: make_user(role=UserRole.CA, is_active=False) -> User (needs `database`)
    auth_headers auth_headers(user) -> {"Authorization": "Bearer <access token>"}

Rate-limit counters are cleared before every test (autouse), so login tests
never hit the limit because of earlier tests.

The test database (TEST_DATABASE_URL, default `ca_helper_test`) is created
automatically if it does not exist. It needs `make infra` to be running.
"""

import shutil

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app import create_app
from app.core.auth.models import User
from app.core.auth.tokens import issue_access_token
from app.core.db.enums import UserRole
from app.core.security.passwords import hash_password
from app.extensions import db as _db
from app.extensions import limiter

TEST_PASSWORD = "Correct-Horse-9"


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
    """Create the test database and all tables once per test session."""
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

    _db.drop_all()  # start clean even if an earlier run was interrupted
    _db.create_all()
    yield _db
    _db.session.remove()
    _db.drop_all()


@pytest.fixture()
def database(_schema):
    """The test database. After the test, every row in every table is deleted.

    Tests use the real db.session, so services commit as usual. Deleting the rows
    afterwards (children before parents, because of foreign keys) means every test
    starts with empty tables.
    """
    yield _schema
    _schema.session.remove()  # drop anything the test left in the session
    with _schema.engine.begin() as conn:
        for table in reversed(_schema.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture(autouse=True)
def _reset_rate_limits(app):
    limiter.reset()


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


def pytest_runtest_setup(item):
    """Skip `@pytest.mark.requires_tesseract` tests when Tesseract is not installed."""
    if item.get_closest_marker("requires_tesseract") and shutil.which("tesseract") is None:
        pytest.skip(
            "Tesseract not found on PATH. Run tests via `make test` (the conda env "
            "provides it) or install tesseract-ocr."
        )
