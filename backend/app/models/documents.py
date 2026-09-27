"""Document tables: uploaded files (metadata only) and their links to filings.

    documents                  one uploaded file's metadata (Document)
    compliance_item_documents  a file serving one filing, N-N (ComplianceItemDocument)

The file itself is encrypted on disk under `storage_key` (rule 4); the database holds
metadata only. A document is OWNED by a user (the business owner, or a CA for their
Certificate of Practice) and UPLOADED by a user, who can differ (a CA uploading an
acknowledgement for a client).
"""

import uuid
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, SoftDeleteMixin
from app.models.enums import str_enum


class DocumentType(StrEnum):
    GST_CERTIFICATE = "gst_certificate"
    PAN_CARD = "pan_card"
    SALES_REGISTER = "sales_register"
    PURCHASE_REGISTER = "purchase_register"
    BANK_STATEMENT = "bank_statement"
    INVOICE = "invoice"
    SALARY_REGISTER = "salary_register"
    TDS_CHALLAN = "tds_challan"
    ACKNOWLEDGEMENT = "acknowledgement"
    CERTIFICATE_OF_PRACTICE = "certificate_of_practice"
    OTHER = "other"


class OcrStatus(StrEnum):
    NONE = "none"  # not run (yet)
    PROCESSED = "processed"
    FAILED = "failed"


class Document(SoftDeleteMixin, BaseModel):
    """One uploaded file's metadata."""

    __tablename__ = "documents"
    __table_args__ = (CheckConstraint("size_bytes >= 0", name="size_not_negative"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    doc_type: Mapped[DocumentType] = mapped_column(str_enum(DocumentType))
    original_filename: Mapped[str] = mapped_column(String(255))
    # Where the encrypted file lives in storage (never a user-supplied path).
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))  # of the original file
    fy: Mapped[str | None] = mapped_column(String(7))  # e.g. "2026-27"
    period_label: Mapped[str | None] = mapped_column(String(30))  # e.g. "Apr 2026"
    ocr_status: Mapped[OcrStatus] = mapped_column(str_enum(OcrStatus), default=OcrStatus.NONE)
    # What OCR extracted, e.g. {"arn": "...", "filed_on": "2026-05-11"}.
    ocr_fields: Mapped[dict | None] = mapped_column(JSONB)


class ComplianceItemDocument(BaseModel):
    """A document serving a filing. One file can serve several filings.

    `checklist_key` is the checklist entry it answers, or "general". Unlinking deletes
    the row (not soft).
    """

    __tablename__ = "compliance_item_documents"
    __table_args__ = (
        UniqueConstraint("compliance_item_id", "document_id", "checklist_key"),
        CheckConstraint("checklist_key <> ''", name="checklist_key_not_empty"),
    )

    compliance_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("compliance_items.id"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    checklist_key: Mapped[str] = mapped_column(
        String(50), default="general", server_default="general"
    )
    linked_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
