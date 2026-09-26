"""Shared model building blocks: every table's model subclasses `BaseModel`.

    class Widget(BaseModel):                     # id + created_at + updated_at
        __tablename__ = "widgets"

    class Document(SoftDeleteMixin, BaseModel):  # ... + is_active + deleted_at
        __tablename__ = "documents"

Models hold data only: columns, relationships and constraints. Logic (including
soft-deleting a row) lives in app/services/. See docs/PATTERNS.md, "Foundations".
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime (CLAUDE.md rule 7)."""
    return datetime.now(UTC)


class TimestampMixin:
    """`created_at` and `updated_at`, stored as timezone-aware UTC.

    Python sets both on insert and `updated_at` on every ORM update; the
    database default `now()` covers rows inserted with raw SQL.
    Bulk `UPDATE` statements bypass `onupdate`, so set `updated_at` there yourself.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )


class SoftDeleteMixin:
    """Opt-in soft delete (CLAUDE.md rule 6): rows are never removed.

    A service soft-deletes a row by setting `is_active = False` and
    `deleted_at = utcnow()`, then commits. Queries for live rows filter on
    `is_active`.
    """

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BaseModel(TimestampMixin, db.Model):
    """Abstract base for every table: UUID primary key plus timestamps.

    The UUID is generated in Python (uuid4) and stored in Postgres's native
    `uuid` type; the API sends it as a string.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
