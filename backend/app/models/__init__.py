"""Database models (SQLAlchemy), one file per table or group of related tables.

    base.py   BaseModel (UUID id + timestamps), SoftDeleteMixin, utcnow()
    enums.py  str_enum() and the enums shared by several models (UserRole)
    user.py   User (`users`)

Every model is imported here, so Alembic (`make migration`) sees every table.
Import a new model here when you add its file.
"""

from app.models.user import User

__all__ = ["User"]
