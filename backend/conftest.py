"""Shared pytest fixtures for ALL backend tests.

This file sits in backend/ (not backend/tests/) on purpose: pytest applies a
conftest.py only to its own folder and below, and tests live both in
backend/tests/ and in app/modules/<module>/tests/.

Fixtures:
    app       Flask app built with TestingConfig (one per test session)
    client    Flask test client for calling the API
    database  test database with every table created; rows are deleted after
              each test. Request it in any test that touches the DB.

The test database (TEST_DATABASE_URL, default `ca_helper_test`) is created
automatically if it does not exist. It needs `make infra` to be running.
"""

import shutil

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app import create_app
from app.extensions import db as _db


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

    with _db.engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    _db.create_all()
    yield _db
    _db.session.remove()
    _db.drop_all()


@pytest.fixture()
def database(_schema):
    yield _schema
    # Clean up: delete all rows (children before parents) so tests stay independent.
    _schema.session.rollback()
    for table in reversed(_schema.metadata.sorted_tables):
        _schema.session.execute(table.delete())
    _schema.session.commit()


def pytest_runtest_setup(item):
    """Skip `@pytest.mark.requires_tesseract` tests when Tesseract is not installed."""
    if item.get_closest_marker("requires_tesseract") and shutil.which("tesseract") is None:
        pytest.skip(
            "Tesseract not found on PATH. Run tests via `make test-backend` (the conda env "
            "provides it) or install tesseract-ocr."
        )
