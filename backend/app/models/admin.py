"""Admin tables: the audit log of admin actions.

    admin_audit_log  one action by an admin (AdminAuditLog)

The target is recorded by type and id (no foreign key), so any table can be a target.
Rows are only ever added, never changed or deleted.
"""

import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AdminAuditLog(BaseModel):
    """One admin action, e.g. verifying a CA or editing a penalty rule."""

    __tablename__ = "admin_audit_log"

    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100))  # e.g. "ca_profile.verify"
    target_type: Mapped[str] = mapped_column(String(50))  # e.g. "ca_profile"
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    details: Mapped[dict | None] = mapped_column(JSONB)  # never PII or document contents
