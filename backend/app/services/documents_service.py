"""Business logic for documents: uploaded files and their metadata.

add_document(owner_id, uploaded_by_id, upload, doc_type) -> Document   store a file (no commit)
read_document(document_id) -> (Document, bytes)                        its metadata and contents
remove_document(document_id)                                           soft delete (no commit)
document_ids_for_filings(filing_ids) -> set                            documents linked to filings

The file itself is encrypted in storage (app/utils/storage.py); the `documents` row
keeps its name, type, size and SHA-256. Who may read a document is decided by the
calling module (e.g. only admins read a CA's certificate).
"""

import hashlib
import logging

from sqlalchemy import select

from app.errors import ApiError
from app.extensions import db
from app.models import ComplianceItemDocument, Document
from app.models.base import utcnow
from app.models.documents import DocumentType
from app.utils import storage

log = logging.getLogger(__name__)


def add_document(owner_id, uploaded_by_id, upload, doc_type: DocumentType) -> Document:
    """Store an uploaded file (a werkzeug FileStorage) and add its row. Does not commit.

    The storage errors (FILE_EMPTY, FILE_TYPE_NOT_ALLOWED, FILE_TOO_LARGE) pass through.
    """
    data = upload.read()
    key = storage.save_file(data, upload.mimetype)
    document = Document(
        owner_id=owner_id,
        uploaded_by_id=uploaded_by_id,
        doc_type=doc_type,
        original_filename=(upload.filename or "upload")[:255],
        storage_key=key,
        mime_type=upload.mimetype,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    db.session.add(document)
    log.info("Stored a %s document (%d bytes)", doc_type, len(data))
    return document


def read_document(document_id) -> tuple[Document, bytes]:
    """A live document and its decrypted contents. 404 DOCUMENT_NOT_FOUND."""
    document = db.session.get(Document, document_id) if document_id else None
    if document is None or document.deleted_at is not None:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "This document was not found.")
    return document, storage.open_file(document.storage_key)


def remove_document(document_id) -> None:
    """Soft-delete a document (the encrypted file stays). Does not commit."""
    document = db.session.get(Document, document_id)
    if document is not None and document.deleted_at is None:
        document.is_active = False
        document.deleted_at = utcnow()


def document_ids_for_filings(filing_ids) -> set:
    """The ids of the live documents linked to any of these filings (compliance_item_documents).

    Used by marketplace to decide which documents a CA may open (MA14).
    """
    stmt = (
        select(ComplianceItemDocument.document_id)
        .join(Document, ComplianceItemDocument.document_id == Document.id)
        .where(
            ComplianceItemDocument.compliance_item_id.in_(filing_ids),
            Document.deleted_at.is_(None),
        )
    )
    return set(db.session.scalars(stmt))
