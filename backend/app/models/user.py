"""The `users` table: one login account per person (business owner, CA or admin).

Email verification (OTP) columns come with the signup task; add them with a new
migration then.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, SoftDeleteMixin
from app.models.enums import UserRole, str_enum


class User(SoftDeleteMixin, BaseModel):
    """A login account (business owner, CA or admin)."""

    __tablename__ = "users"

    # Stored normalized (trimmed, lowercased) by auth_service.normalize_email().
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))  # argon2, never the password
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(str_enum(UserRole))
