"""BaseModel, the timestamp/soft-delete mixins, str_enum() and per-test rollback."""

import uuid
from datetime import timedelta
from enum import StrEnum

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, StatementError

from app.core.db.enums import str_enum
from app.extensions import db
from tests._models import Gadget, GadgetColour


def create_gadget(name: str = "Stapler", colour: GadgetColour = GadgetColour.RED) -> Gadget:
    """Stands in for a service function: one unit of work that commits at its end."""
    gadget = Gadget(name=name, colour=colour)
    db.session.add(gadget)
    db.session.commit()
    return gadget


# --- BaseModel and mixins -------------------------------------------------------


def test_base_model_gives_uuid_id_and_utc_timestamps(database):
    gadget = create_gadget()

    assert isinstance(gadget.id, uuid.UUID)
    assert gadget.created_at.utcoffset() == timedelta(0)
    assert gadget.updated_at.utcoffset() == timedelta(0)
    column_type = db.session.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'test_gadgets' AND column_name = 'id'"
        )
    ).scalar_one()
    assert column_type == "uuid"


def test_updated_at_changes_on_update(database):
    gadget = create_gadget()
    created_at, first_updated_at = gadget.created_at, gadget.updated_at

    gadget.name = "Hole punch"
    db.session.commit()

    assert gadget.updated_at > first_updated_at
    assert gadget.created_at == created_at


def test_soft_delete_mixin_defaults_to_active(database):
    gadget = create_gadget()

    assert gadget.is_active is True
    assert gadget.deleted_at is None


def test_database_defaults_cover_raw_sql_inserts(database):
    db.session.execute(
        text("INSERT INTO test_gadgets (id, name, colour) VALUES (:id, 'Raw', 'red')"),
        {"id": uuid.uuid4()},
    )

    row = db.session.execute(
        text("SELECT created_at, updated_at, is_active FROM test_gadgets WHERE name = 'Raw'")
    ).one()
    assert row.created_at is not None
    assert row.updated_at is not None
    assert row.is_active is True


# --- str_enum() -----------------------------------------------------------------


def test_enum_stores_the_value_and_loads_the_member(database):
    gadget = create_gadget(colour=GadgetColour.DARK_BLUE)
    db.session.expire_all()

    stored = db.session.execute(
        text("SELECT colour FROM test_gadgets WHERE id = :id"), {"id": gadget.id}
    ).scalar_one()
    assert stored == "dark_blue"  # the value, not the member name DARK_BLUE
    assert db.session.get(Gadget, gadget.id).colour is GadgetColour.DARK_BLUE


def test_enum_rejects_unknown_value_in_the_orm(database):
    db.session.add(Gadget(name="Bad", colour="purple"))

    with pytest.raises(StatementError):
        db.session.flush()
    db.session.rollback()


def test_enum_check_constraint_rejects_unknown_value_in_raw_sql(database):
    with pytest.raises(IntegrityError, match="ck_test_gadgets_gadget_colour"):
        db.session.execute(
            text("INSERT INTO test_gadgets (id, name, colour) VALUES (:id, 'Bad', 'purple')"),
            {"id": uuid.uuid4()},
        )
    db.session.rollback()


def test_enum_check_constraint_has_a_stable_name(database):
    names = db.session.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'test_gadgets'::regclass AND contype = 'c'"
        )
    ).scalars()
    assert set(names) == {"ck_test_gadgets_gadget_colour"}


def test_enum_values_must_be_lowercase_snake_case():
    class BadStatus(StrEnum):
        DOCS_PENDING = "Docs pending"

    with pytest.raises(ValueError, match="lowercase snake_case"):
        str_enum(BadStatus)


def test_enum_constraint_name_can_be_overridden():
    assert str_enum(GadgetColour, name="paint").name == "paint"


# --- Per-test transaction with savepoints (conftest.py `database`) ---------------


def test_service_commit_is_not_visible_outside_the_test_transaction(database):
    create_gadget()

    assert db.session.scalar(select(func.count()).select_from(Gadget)) == 1
    # A separate connection sees only committed data: our "commit" only released a
    # savepoint inside the outer transaction, which the fixture rolls back.
    with db.engine.connect() as other_connection:
        count = other_connection.execute(text("SELECT count(*) FROM test_gadgets")).scalar()
    assert count == 0


def test_rollback_after_a_commit_keeps_committed_rows(database):
    create_gadget(name="Kept")
    db.session.add(Gadget(name="Broken", colour="purple"))
    with pytest.raises(StatementError):
        db.session.flush()

    db.session.rollback()  # back to the last savepoint, not the start of the test

    assert db.session.scalars(select(Gadget.name)).all() == ["Kept"]


def test_rows_from_earlier_tests_are_gone(database):
    # Earlier tests in this file committed gadgets; each was rolled back after its test.
    assert db.session.scalar(select(func.count()).select_from(Gadget)) == 0
