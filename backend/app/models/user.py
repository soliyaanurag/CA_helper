"""The `users` table: one login account per person (business owner, CA or admin)."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class User(BaseModel):
    """A login account (business owner, CA or admin)."""

    __tablename__ = "users"

    # Stored normalized (trimmed, lowercased) by auth_service.normalize_email().
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))  # argon2, never the password
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(50))
    # Set when the user enters the code we emailed them; login is refused while it is empty.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When the user accepted the terms (set by signup in a later task; empty until then).
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

