"""The `email_otps` table: 6-digit one-time codes sent by email.

A code verifies a new account's email or lets a user reset a forgotten password
(`purpose`). Only the user's newest code for a purpose counts. The code itself is
never stored, only its argon2 hash. Rows are never deleted: a used code gets
`used_at`. The rules (lifetime, attempts, resend wait) are in auth_service.py.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import str_enum
from app.models.user import User


class OtpPurpose(StrEnum):
    """What a one-time code is for."""

    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"


class EmailOtp(BaseModel):
    """One code emailed to a user."""

    __tablename__ = "email_otps"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    user: Mapped[User] = relationship()
    purpose: Mapped[OtpPurpose] = mapped_column(str_enum(OtpPurpose))
    code_hash: Mapped[str] = mapped_column(String(255))  # argon2 hash of the 6 digits
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Wrong guesses so far; the code stops working at auth_service.OTP_MAX_ATTEMPTS.
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
