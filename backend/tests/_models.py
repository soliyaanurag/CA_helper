"""A test-only model for the database foundation tests. Never used by the app.

It lives under tests/, so the app (and therefore Alembic) never imports it; the
`_schema` fixture creates its table in the test database only.
"""

from enum import StrEnum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, SoftDeleteMixin
from app.models.enums import str_enum


class GadgetColour(StrEnum):
    RED = "red"
    DARK_BLUE = "dark_blue"


class Gadget(SoftDeleteMixin, BaseModel):
    __tablename__ = "test_gadgets"

    name: Mapped[str] = mapped_column(String(50))
    colour: Mapped[GadgetColour] = mapped_column(str_enum(GadgetColour))
