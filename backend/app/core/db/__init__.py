"""Database foundations (see docs/PATTERNS.md, "Foundations").

    base.py    declarative Base with deterministic constraint names (for Alembic)
    models.py  BaseModel (UUID id + created_at/updated_at), TimestampMixin,
               SoftDeleteMixin (is_active/deleted_at), utcnow()
    enums.py   str_enum(): StrEnum columns stored as text + a CHECK constraint

Planned: money helpers (Decimal, Numeric(12, 2) rupees).
"""
