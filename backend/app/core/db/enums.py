"""Enum columns stored as plain text plus a CHECK constraint.

    class ComplianceStatus(StrEnum):
        UPCOMING = "upcoming"
        DOCS_PENDING = "docs_pending"

    status: Mapped[ComplianceStatus] = mapped_column(str_enum(ComplianceStatus))

- The database stores the enum's VALUES ("docs_pending"), never the member
  names, in a VARCHAR column (no Postgres ENUM type, which is hard to migrate).
- A CHECK constraint named `ck_<table>_<enum name>` (from the naming convention
  in base.py) rejects any other value, even from raw SQL.
- Write values in lowercase snake_case; display text lives in the frontend label
  map (frontend/src/core/labels.ts) and docs/DATA_MODEL.md.
- Adding a value later needs a hand-written migration that replaces the CHECK
  constraint: Alembic autogenerate does not detect CHECK changes.
"""

import re
from enum import StrEnum

import sqlalchemy as sa

# Room for future values without altering the column; the CHECK constraint is
# what restricts the allowed values.
ENUM_COLUMN_LENGTH = 50


def _snake_case(name: str) -> str:
    """ComplianceStatus -> compliance_status."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def str_enum(enum_cls: type[StrEnum], name: str | None = None) -> sa.Enum:
    """SQLAlchemy column type for a StrEnum: text values plus a CHECK constraint.

    `name` names the CHECK constraint; it defaults to the enum class name in
    snake_case. Pass it when one table has two columns of the same enum.
    """
    return sa.Enum(
        enum_cls,
        name=name or _snake_case(enum_cls.__name__),
        native_enum=False,  # VARCHAR, not a Postgres ENUM type
        create_constraint=True,  # CHECK (col IN (...values))
        validate_strings=True,  # reject unknown strings before they reach the DB
        values_callable=lambda cls: [member.value for member in cls],  # store values
        length=ENUM_COLUMN_LENGTH,
    )


# --- Shared enums ---------------------------------------------------------------
# Enums used by more than one module live here; a module's own enums live in its
# models.py. Codes and labels: docs/DATA_MODEL.md, "Status values".


class UserRole(StrEnum):
    """Who a login account belongs to; also the `role` claim in the JWT."""

    BUSINESS = "business"
    CA = "ca"
    ADMIN = "admin"
