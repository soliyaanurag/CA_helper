"""CA workspace tables: a CA's document requests to clients, and private notes.

    document_requests  a CA asking a client for a document for one filing (DocumentRequest)
    ca_notes           a CA's private note about a client (CaNote)

Service rule: a document request's compliance item must belong to its engagement
(an engagement_items row). A client never sees a CA's notes.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class DocumentRequestStatus(StrEnum):
    OPEN = "open"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class DocumentRequest(BaseModel):
    """A CA's request for one document, shown to the business as a to-do."""

    __tablename__ = "document_requests"

    engagement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engagements.id"), index=True)
    compliance_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compliance_items.id"))
    # The checklist entry asked for (content/forms/<FORM>/checklist.yaml), or "general".
    checklist_key: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(
        String(50), default=DocumentRequestStatus.OPEN
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The file that answered it (empty until fulfilled).
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))


class CaNote(BaseModel):
    """A CA's private note about one client business."""

    __tablename__ = "ca_notes"
    __table_args__ = (
        Index("ix_ca_notes_ca_profile_id_business_id", "ca_profile_id", "business_id"),
    )

    ca_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ca_profiles.id"))
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"))
    body: Mapped[str] = mapped_column(Text)
