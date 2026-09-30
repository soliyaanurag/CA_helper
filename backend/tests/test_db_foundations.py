"""BaseModel, the timestamp mixin, enum values stored as text, and per-test cleanup."""

import uuid
from datetime import timedelta

from sqlalchemy import func, select, text

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


def test_database_defaults_cover_raw_sql_inserts(database):
    db.session.execute(
        text("INSERT INTO test_gadgets (id, name, colour) VALUES (:id, 'Raw', 'red')"),
        {"id": uuid.uuid4()},
    )

    row = db.session.execute(
        text("SELECT created_at, updated_at FROM test_gadgets WHERE name = 'Raw'")
    ).one()
    assert row.created_at is not None
    assert row.updated_at is not None


# --- Enum values in plain text columns -------------------------------------------


def test_enum_stores_the_value(database):
    gadget = create_gadget(colour=GadgetColour.DARK_BLUE)
    db.session.expire_all()

    stored = db.session.execute(
        text("SELECT colour FROM test_gadgets WHERE id = :id"), {"id": gadget.id}
    ).scalar_one()
    assert stored == "dark_blue"  # the value, not the member name DARK_BLUE
    assert db.session.get(Gadget, gadget.id).colour == GadgetColour.DARK_BLUE


# --- Per-test cleanup (conftest.py `database`) ------------------------------------


def test_rows_from_earlier_tests_are_gone(database):
    # Earlier tests in this file committed gadgets; each was deleted after its test.
    assert db.session.scalar(select(func.count()).select_from(Gadget)) == 0
