"""Business logic for documents: uploaded files, the vault and their links to filings.

Used by other modules (no commit):
add_document(owner_id, uploaded_by_id, upload, doc_type) -> Document   store a file
on_document_uploaded(document)                                         hook for OCR (a no-op)
read_document(document_id) -> (Document, bytes)                        its metadata and contents
remove_document(document_id)                                           soft delete
document_ids_for_filings(filing_ids) -> set                            documents linked to filings

The vault (routes/documents.py):
upload_document(business, user, upload, doc_type, ...) -> dict  upload, maybe link it (DO2, DO6)
list_documents(business, page, page_size, ...) -> dict          the business's files (DO3)
get_document_file(user, document_id) -> (Document, bytes)       owner or allowed CA (DO4, DO7)
delete_document(business, document_id)                          soft delete, unless proof (DO5)
link_document(business, user, document_id, item_id, key) -> dict  a file serves a filing (DO6)
unlink_document(business, link_id)                              remove that link (DO6)

The file itself is encrypted in storage (app/utils/storage.py); the `documents` row
keeps its name, type, size and SHA-256. A document is linked to a filing per checklist
key (`compliance_item_documents`), or with the key "general" when it answers no
checklist entry; one file can serve several filings. Linking a file to a checklist
entry also ticks that entry. Once a filing is filed, its links are fixed: they are the
proof of what was filed.

documents <-> compliance and documents <-> marketplace import each other's service
modules (`from app.services import ...`); that works because none of them calls the
other while it is being imported.
"""

import hashlib
import logging

from sqlalchemy import or_, select

from app.errors import ApiError
from app.extensions import db
from app.models import ComplianceItemDocument, Document, User
from app.models.base import utcnow
from app.models.documents import DocumentType
from app.models.enums import UserRole
from app.services import compliance_service, marketplace_service
from app.utils import storage

log = logging.getLogger(__name__)

# The checklist key of a link that answers no checklist entry.
GENERAL_KEY = "general"


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
    db.session.flush()  # gives document.id
    log.info("Stored a %s document (%d bytes)", doc_type, len(data))
    on_document_uploaded(document)
    return document


def on_document_uploaded(document: Document) -> None:
    """Called for every new document, right after its row is added. Does not commit.

    A no-op for now: this is where local OCR (DO8, DO9) will read the file and fill
    `ocr_status` and `ocr_fields`. It must never send the file anywhere (rule 2).
    """


def read_document(document_id) -> tuple[Document, bytes]:
    """A live document and its decrypted contents. 404 DOCUMENT_NOT_FOUND."""
    document = _live_document(document_id)
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


# --- The vault (DO2 to DO7) -----------------------------------------------------------


def _live_document(document_id) -> Document:
    """A live document. 404 DOCUMENT_NOT_FOUND."""
    document = db.session.get(Document, document_id) if document_id else None
    if document is None or document.deleted_at is not None:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "This document was not found.")
    return document


def _own_document(business, document_id) -> Document:
    """One live document of this business's owner. 404 DOCUMENT_NOT_FOUND for anyone else's."""
    document = _live_document(document_id)
    if document.owner_id != business.user_id:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "This document was not found.")
    return document


def _filing_name(filing) -> str:
    """e.g. "GSTR-3B (Q1 2026-27)", for messages."""
    return f"{compliance_service.FORM_FOLDERS[filing.form_code]} ({filing.period_label})"


def _open_filing(business, item_id):
    """A live filing of this business whose documents may still change.

    404 FILING_NOT_FOUND for anyone else's; 409 FILING_LOCKED once it is filed.
    """
    filing = compliance_service.get_filings_by_ids([item_id]).get(item_id)
    if filing is None or filing.business_id != business.id:
        raise ApiError(404, "FILING_NOT_FOUND", "This filing was not found.")
    if filing.status in compliance_service.DONE_STATUSES:
        raise ApiError(
            409, "FILING_LOCKED", "This filing is filed, so its documents can no longer change."
        )
    return filing


def _check_key(filing, checklist_key: str) -> None:
    """422 UNKNOWN_CHECKLIST_KEY unless the key is "general" or in the form's checklist."""
    if checklist_key != GENERAL_KEY and checklist_key not in compliance_service.checklist_keys(
        filing.form_code
    ):
        raise ApiError(422, "UNKNOWN_CHECKLIST_KEY", "This checklist entry does not exist.")


def _link(filing, document: Document, checklist_key: str, user: User) -> None:
    """Link the document to the filing (once) and tick the checklist entry. Does not commit."""
    existing = db.session.scalar(
        select(ComplianceItemDocument).where(
            ComplianceItemDocument.compliance_item_id == filing.id,
            ComplianceItemDocument.document_id == document.id,
            ComplianceItemDocument.checklist_key == checklist_key,
        )
    )
    if existing is None:
        db.session.add(
            ComplianceItemDocument(
                compliance_item_id=filing.id,
                document_id=document.id,
                checklist_key=checklist_key,
                linked_by_id=user.id,
            )
        )
    if checklist_key != GENERAL_KEY:
        compliance_service.tick_checklist_entry(filing, checklist_key)


def _links_of(document_ids) -> list[ComplianceItemDocument]:
    if len(document_ids) == 0:
        return []
    stmt = select(ComplianceItemDocument).where(
        ComplianceItemDocument.document_id.in_(document_ids)
    )
    return list(db.session.scalars(stmt))


def _describe(documents) -> list[dict]:
    """Each document's fields plus the filings it serves: `links` (with the checklist key)
    and `acknowledgement_of` (the filings it is the acknowledgement of)."""
    document_ids = [document.id for document in documents]
    links = _links_of(document_ids)
    acknowledged = compliance_service.filings_by_acknowledgement(document_ids)
    filings = compliance_service.get_filings_by_ids({link.compliance_item_id for link in links})

    rows = []
    for document in documents:
        row = {
            "id": document.id,
            "doc_type": document.doc_type,
            "original_filename": document.original_filename,
            "mime_type": document.mime_type,
            "size_bytes": document.size_bytes,
            "fy": document.fy,
            "period_label": document.period_label,
            "ocr_status": document.ocr_status,
            "created_at": document.created_at,
            "links": [],
            "acknowledgement_of": [],
        }
        for link in links:
            filing = filings.get(link.compliance_item_id)
            if link.document_id == document.id and filing is not None:
                row["links"].append(
                    {
                        "id": link.id,
                        "compliance_item_id": filing.id,
                        "form_code": filing.form_code,
                        "period_label": filing.period_label,
                        "checklist_key": link.checklist_key,
                    }
                )
        filing = acknowledged.get(document.id)
        if filing is not None:
            row["acknowledgement_of"].append(
                {
                    "compliance_item_id": filing.id,
                    "form_code": filing.form_code,
                    "period_label": filing.period_label,
                }
            )
        rows.append(row)
    return rows


def upload_document(
    business,
    user: User,
    upload,
    doc_type: DocumentType,
    fy=None,
    period_label=None,
    item_id=None,
    checklist_key=None,
) -> dict:
    """Upload a file to the vault (DO2); with `item_id`, also link it to that filing under
    `checklist_key` ("general" if not given) (DO6). A linked file without its own FY or
    period gets the filing's.

    404 FILING_NOT_FOUND, 409 FILING_LOCKED, 422 UNKNOWN_CHECKLIST_KEY (checked before the
    file is stored); the storage errors (FILE_EMPTY, FILE_TYPE_NOT_ALLOWED, FILE_TOO_LARGE).
    """
    filing = None
    if item_id is not None:
        filing = _open_filing(business, item_id)
        checklist_key = checklist_key or GENERAL_KEY
        _check_key(filing, checklist_key)

    document = add_document(business.user_id, user.id, upload, doc_type)
    document.fy = fy
    document.period_label = period_label
    if filing is not None:
        document.fy = fy or filing.fy
        document.period_label = period_label or filing.period_label
        _link(filing, document, checklist_key, user)
    db.session.commit()
    return _describe([document])[0]


def list_documents(
    business, page: int, page_size: int, fy=None, doc_type=None, compliance_item_id=None
) -> dict:
    """The business's live documents, newest first, paginated (DO3).

    Filters: financial year, type, and a filing (the documents linked to it and its
    acknowledgement).
    """
    stmt = select(Document).where(
        Document.owner_id == business.user_id, Document.deleted_at.is_(None)
    )
    if fy is not None:
        stmt = stmt.where(Document.fy == fy)
    if doc_type is not None:
        stmt = stmt.where(Document.doc_type == doc_type)
    if compliance_item_id is not None:
        linked = select(ComplianceItemDocument.document_id).where(
            ComplianceItemDocument.compliance_item_id == compliance_item_id
        )
        filing = compliance_service.get_filings_by_ids([compliance_item_id]).get(compliance_item_id)
        acknowledgement_id = filing.acknowledgement_document_id if filing is not None else None
        stmt = stmt.where(or_(Document.id.in_(linked), Document.id == acknowledgement_id))
    stmt = stmt.order_by(Document.created_at.desc(), Document.id)

    result = db.paginate(stmt, page=page, per_page=page_size, error_out=False)
    return {
        "items": _describe(result.items),
        "page": page,
        "page_size": page_size,
        "total": result.total,
    }


def get_document_file(user: User, document_id) -> tuple[Document, bytes]:
    """A document and its decrypted contents, for its owner, or for a CA whose ACTIVE
    engagement covers a filing it serves (ca_can_access_document, DO7).

    404 DOCUMENT_NOT_FOUND for everyone else (they do not learn that it exists).
    """
    document = _live_document(document_id)
    allowed = document.owner_id == user.id
    if not allowed and user.role == UserRole.CA:
        ca_profile_id = marketplace_service.own_profile_id(user)
        allowed = ca_profile_id is not None and marketplace_service.ca_can_access_document(
            ca_profile_id, document.id
        )
    if not allowed:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "This document was not found.")
    log.info("Document %s opened by user %s", document.id, user.id)
    return document, storage.open_file(document.storage_key)


def delete_document(business, document_id) -> None:
    """Soft-delete one of the business's documents and remove its links (DO5).

    409 DOCUMENT_IN_USE when it is a filing's acknowledgement or linked to a filed
    filing: it is the proof of that filing.
    """
    document = _own_document(business, document_id)
    acknowledged = compliance_service.filings_by_acknowledgement([document.id]).get(document.id)
    if acknowledged is not None:
        raise ApiError(
            409,
            "DOCUMENT_IN_USE",
            f"This is the acknowledgement of {_filing_name(acknowledged)}. "
            'Undo "mark as filed" on that filing to remove it.',
        )
    links = _links_of([document.id])
    filings = compliance_service.get_filings_by_ids({link.compliance_item_id for link in links})
    for filing in filings.values():
        if filing.status in compliance_service.DONE_STATUSES:
            raise ApiError(
                409,
                "DOCUMENT_IN_USE",
                f"This document is proof for {_filing_name(filing)}, which is filed, "
                "so it cannot be deleted.",
            )
    for link in links:
        db.session.delete(link)
    remove_document(document.id)
    db.session.commit()
    log.info("Document %s deleted", document.id)


def link_document(business, user: User, document_id, item_id, checklist_key: str) -> dict:
    """Link one of the business's documents to one of its filings (DO6). Linking it twice
    changes nothing. A checklist key (not "general") is ticked.

    404 DOCUMENT_NOT_FOUND, FILING_NOT_FOUND; 409 FILING_LOCKED; 422 UNKNOWN_CHECKLIST_KEY.
    """
    document = _own_document(business, document_id)
    filing = _open_filing(business, item_id)
    _check_key(filing, checklist_key)
    _link(filing, document, checklist_key, user)
    db.session.commit()
    return _describe([document])[0]


def unlink_document(business, link_id) -> None:
    """Remove one link between a document and a filing (the row is deleted; the tick stays).

    404 LINK_NOT_FOUND for anyone else's link; 409 FILING_LOCKED once the filing is filed.
    """
    link = db.session.get(ComplianceItemDocument, link_id)
    if link is None:
        raise ApiError(404, "LINK_NOT_FOUND", "This link was not found.")
    document = db.session.get(Document, link.document_id)
    if document.owner_id != business.user_id:
        raise ApiError(404, "LINK_NOT_FOUND", "This link was not found.")
    _open_filing(business, link.compliance_item_id)
    db.session.delete(link)
    db.session.commit()
