"""Request and response shapes for /api/v1/documents/...

Business logic for documents: uploaded files, the vault and their links to filings.

Used by other modules (no commit):
add_document(owner_id, uploaded_by_id, upload, doc_type) -> Document   store a file
on_document_uploaded(document, data)                                   local OCR (ON12, DO8, DO9)
verify_acknowledgement(document, filing) -> dict                       proves the filing? (DO8)
get_document(document_id) -> Document                                 its metadata (404 if missing)
read_document(document_id) -> (Document, bytes)                        its metadata and contents
remove_document(document_id)                                           delete the row and links
document_ids_for_filings(filing_ids) -> set                            documents linked to filings

The vault (routes/documents.py):
upload_document(business, user, upload, doc_type, ...) -> dict  upload, maybe link it (DO2, DO6)
list_documents(business, page, page_size, ...) -> dict          the business's files (DO3)
get_document_file(user, document_id) -> (Document, bytes)       owner or allowed CA (DO4, DO7)
delete_document(business, document_id)                          soft delete, unless proof (DO5)
link_document(business, user, document_id, item_id, key) -> dict  a file serves a filing (DO6)
unlink_document(business, link_id)                              remove that link (DO6)

For ca_workspace: attach_document(...) (link_document without the commit),
documents_by_filing(filings) -> dict (each filing's files and acknowledgement).

The file itself is stored encrypted in `documents.content`, with its name, type, size
and SHA-256. A document is linked to a filing per checklist
key (`compliance_item_documents`), or with the key "general" when it answers no
checklist entry; one file can serve several filings. Linking a file to a checklist
entry also ticks that entry. Once a filing is filed, its links are fixed: they are the
proof of what was filed.

documents <-> compliance and documents <-> marketplace import each other's service
modules (`from app.services import ...`); that works because none of them calls the
other while it is being imported.

HTTP routes for documents: /api/v1/documents/...

    POST   /documents                  upload a file, optionally linked to a filing (DO2, DO6)
    GET    /documents?fy=&doc_type=&compliance_item_id=&page=   my vault (DO3)
    GET    /documents/<id>/file        the file itself: its owner, or a CA allowed by an
                                       ACTIVE engagement (DO4, DO7)
    DELETE /documents/<id>             soft delete, unless it is proof of a filing (DO5)
    POST   /documents/<id>/links       link it to a filing's checklist entry (DO6)
    DELETE /documents/links/<link_id>  unlink it (DO6)

Admins never read document contents (rule 5): they are not allowed on these routes.
Routes stay thin: parse input (app/schemas/), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

import hashlib
import io
import logging
import re
from datetime import date

from flask import send_file
from flask_smorest import Blueprint
from marshmallow import fields, post_load, Schema, validate, ValidationError
from sqlalchemy import delete, or_, select, update

from app import compliance, marketplace, ocr, utils
from app.models import (
    ComplianceItemDocument,
    db,
    decrypt_bytes,
    Document,
    DocumentRequest,
    DocumentType,
    encrypt_bytes,
    FormCode,
    OcrStatus,
    today_in_india,
    User,
    UserRole,
)
from app.utils import (
    ApiError,
    current_business,
    current_user,
    ErrorSchema,
    PageArgsSchema,
    PageSchema,
    roles_required,
)


# --- Request and response shapes ---------------------------------------------------------


# A financial year is written "2026-27": April 2026 to March 2027.
FY_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


def _check_fy(value: str) -> None:
    match = FY_PATTERN.match(value)
    if match is None or (int(match.group(1)) + 1) % 100 != int(match.group(2)):
        raise ValidationError('Write the financial year like "2026-27".')


class DocumentLinkSchema(Schema):
    id = fields.UUID(required=True, metadata={"description": "The link's id (to unlink it)"})
    compliance_item_id = fields.UUID(required=True)
    form_code = fields.String(validate=validate.OneOf(list(FormCode)), required=True)
    period_label = fields.String(required=True)
    checklist_key = fields.String(required=True, metadata={"description": 'or "general"'})


class AcknowledgedFilingSchema(Schema):
    compliance_item_id = fields.UUID(required=True)
    form_code = fields.String(validate=validate.OneOf(list(FormCode)), required=True)
    period_label = fields.String(required=True)


class DocumentSchema(Schema):
    id = fields.UUID(required=True)
    doc_type = fields.String(validate=validate.OneOf(list(DocumentType)), required=True)
    original_filename = fields.String(required=True)
    mime_type = fields.String(required=True)
    size_bytes = fields.Integer(required=True)
    fy = fields.String(allow_none=True, metadata={"description": 'e.g. "2026-27"'})
    period_label = fields.String(allow_none=True, metadata={"description": 'e.g. "Apr 2026"'})
    ocr_status = fields.String(validate=validate.OneOf(list(OcrStatus)), required=True)
    type_warning = fields.String(
        allow_none=True,
        metadata={"description": "What the file looks like when it differs from doc_type (DO9)"},
    )
    created_at = fields.DateTime(required=True)
    links = fields.List(
        fields.Nested(DocumentLinkSchema),
        required=True,
        metadata={"description": "The filings (and checklist entries) this file serves"},
    )
    acknowledgement_of = fields.List(
        fields.Nested(AcknowledgedFilingSchema),
        required=True,
        metadata={"description": "The filings this file is the acknowledgement of"},
    )


class DocumentPageSchema(PageSchema):
    items = fields.List(fields.Nested(DocumentSchema), required=True)


class DocumentListArgsSchema(PageArgsSchema):
    fy = fields.String(load_default=None, validate=_check_fy)
    doc_type = fields.String(validate=validate.OneOf(list(DocumentType)), load_default=None)
    compliance_item_id = fields.UUID(
        load_default=None, metadata={"description": "Only the documents of this filing"}
    )


class DocumentUploadFormSchema(Schema):
    """POST /documents (multipart/form-data), the text part."""

    doc_type = fields.String(
        required=True,
        validate=[
            validate.OneOf(list(DocumentType)),
            validate.NoneOf(
                [DocumentType.CERTIFICATE_OF_PRACTICE], error="This type cannot be uploaded here."
            ),
        ],
    )
    fy = fields.String(load_default=None, validate=_check_fy)
    period_label = fields.String(load_default=None, validate=validate.Length(max=30))
    compliance_item_id = fields.UUID(
        load_default=None, metadata={"description": "Also link the file to this filing"}
    )
    checklist_key = fields.String(
        load_default=None,
        validate=validate.Length(1, 50),
        metadata={"description": 'The checklist entry it answers (default "general")'},
    )

    @post_load
    def _clean(self, data: dict, **kwargs) -> dict:
        if data["period_label"] is not None:
            data["period_label"] = data["period_label"].strip() or None
        return data


class DocumentUploadFileSchema(Schema):
    """The file (PDF, JPG or PNG)."""

    file = fields.Raw(required=True, metadata={"type": "string", "format": "binary"})


class DocumentLinkCreateSchema(Schema):
    """POST /documents/<id>/links."""

    compliance_item_id = fields.UUID(required=True)
    checklist_key = fields.String(
        load_default="general",
        validate=validate.Length(1, 50),
        metadata={"description": 'The checklist entry it answers, or "general"'},
    )


# --- Logic -------------------------------------------------------------------------------


log = logging.getLogger(__name__)

# The checklist key of a link that answers no checklist entry.
GENERAL_KEY = "general"
# How documents_by_filing() marks a filing's acknowledgement.
ACKNOWLEDGEMENT_KEY = "acknowledgement"


def add_document(owner_id, uploaded_by_id, upload, doc_type: DocumentType) -> Document:
    """Store an uploaded file (a werkzeug FileStorage) and add its row. Does not commit.

    The file check errors (FILE_EMPTY, FILE_TYPE_NOT_ALLOWED, FILE_TOO_LARGE) pass through.
    """
    data = upload.read()
    utils.check_file(data, upload.mimetype)
    document = Document(
        owner_id=owner_id,
        uploaded_by_id=uploaded_by_id,
        doc_type=doc_type,
        original_filename=(upload.filename or "upload")[:255],
        content=encrypt_bytes(data),
        mime_type=upload.mimetype,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    db.session.add(document)
    db.session.flush()  # gives document.id
    log.info("Stored a %s document (%d bytes)", doc_type, len(data))
    on_document_uploaded(document, data)
    return document


def on_document_uploaded(document: Document, data: bytes) -> None:
    """Read every new file locally and keep what it shows (ON12, DO8, DO9). Does not commit.

    `ocr_fields` gets only non-personal facts (acknowledgement number, filing date, forms,
    periods, a type guess; app/utils/ocr.py). The text itself and any PAN,
    GSTIN or name are never stored, and the file never leaves the server (rules 2, 4).
    OCR never makes an upload fail: an unreadable file is saved with ocr_status "failed".
    """
    try:
        text = ocr.extract_text(data, document.mime_type)
    except ocr.OcrError as error:
        document.ocr_status = OcrStatus.FAILED
        document.ocr_fields = {"error": str(error)}
        return
    except Exception:  # an unexpected library error must not lose the upload
        log.exception("OCR failed for document %s", document.id)
        document.ocr_status = OcrStatus.FAILED
        document.ocr_fields = {"error": "The file could not be read."}
        return
    document.ocr_fields = ocr.read_proof_fields(text, today_in_india())
    document.ocr_status = OcrStatus.PROCESSED


def type_warning(document: Document) -> DocumentType | None:
    """DO9: the type the file looks like when it differs from the type it was uploaded as
    (e.g. "bank_statement" for a file uploaded as an invoice), else None."""
    guess = (document.ocr_fields or {}).get("type_guess")
    if guess is None or guess == document.doc_type or document.doc_type == DocumentType.OTHER:
        return None
    return DocumentType(guess)


def _quarter_months(filing) -> list[tuple[int, int]]:
    """(year, month) of every month of the filing's period, e.g. Jul, Aug, Sep 2026."""
    months = []
    year, month = filing.period_start.year, filing.period_start.month
    while (year, month) <= (filing.period_end.year, filing.period_end.month):
        months.append((year, month))
        month = month + 1
        if month > 12:
            month = 1
            year = year + 1
    return months


def _period_shown(fields: dict, filing) -> bool:
    """Does the acknowledgement show the filing's period?

    A month: "September" with the financial year, or "092026". A quarter: the financial
    year with "Q2" or one of its months. A year: the financial year; an ITR may show the
    assessment year instead (the year after, "2027-28" for FY 2026-27).
    """
    years = fields.get("financial_years", [])
    fy_start = int(filing.fy[:4])
    assessment_year = f"{fy_start + 1}-{str(fy_start + 2)[2:]}"
    months = _quarter_months(filing)
    if len(months) == 12:  # a whole financial year
        return filing.fy in years or (filing.form_code == "itr" and assessment_year in years)
    for year, month in months:
        if f"{year}-{month:02d}" in fields.get("months_with_year", []):
            return True
    if filing.fy not in years:
        return False
    if len(months) == 1:
        return months[0][1] in fields.get("months", [])
    quarter = int(filing.period_label[1]) if filing.period_label.startswith("Q") else None
    named_month = any(month in fields.get("months", []) for _, month in months)
    return quarter in fields.get("quarters", []) or named_month


def verify_acknowledgement(document: Document, filing) -> dict:
    """Does this acknowledgement prove this filing? (DO8)

    It must name the form, show the period, have an acknowledgement / ARN number (the
    same as the one typed, if any) and a filing date on or after the period's end.
    Returns {verified, problems (what did not match, for the page), acknowledgement_no,
    filing_date}.
    """
    fields = document.ocr_fields or {}
    found = {
        "acknowledgement_no": fields.get("acknowledgement_no"),
        "filing_date": fields.get("filing_date"),
    }
    if document.ocr_status != OcrStatus.PROCESSED:
        reason = fields.get("error") or "The file has not been read yet."
        return {"verified": False, "problems": [reason], **found}

    problems = []
    form_name = compliance.form_name(filing.form_code, filing.fy)
    if filing.form_code not in fields.get("form_codes", []):
        problems.append(f"It does not name the form {form_name}.")
    if not _period_shown(fields, filing):
        problems.append(f"It does not show the period {filing.period_label}.")
    number = found["acknowledgement_no"]
    typed = (filing.acknowledgement_no or "").replace(" ", "").upper()
    if number is None:
        problems.append("No acknowledgement or ARN number was found.")
    elif typed and typed != number:
        problems.append(f"Its number ({number}) is not the one typed ({typed}).")
    if found["filing_date"] is None:
        problems.append("No filing date was found.")
    elif date.fromisoformat(found["filing_date"]) < filing.period_end:
        problems.append("Its date is before the end of the period.")
    return {"verified": not problems, "problems": problems, **found}


def read_document(document_id) -> tuple[Document, bytes]:
    """A live document and its decrypted contents. 404 DOCUMENT_NOT_FOUND."""
    document = get_document(document_id)
    return document, decrypt_bytes(document.content)


def remove_document(document_id) -> None:
    """Delete a document: its links and its row (with the file). Does not commit.

    The caller first clears a filing's acknowledgement or a CA's certificate that points to it.
    A document request it answered stays fulfilled, without the file.
    """
    document = db.session.get(Document, document_id)
    if document is None:
        return
    db.session.execute(
        delete(ComplianceItemDocument).where(ComplianceItemDocument.document_id == document.id)
    )
    db.session.execute(
        update(DocumentRequest).where(DocumentRequest.document_id == document.id).values(document_id=None)
    )
    db.session.delete(document)


def document_ids_for_filings(filing_ids) -> set:
    """The ids of the live documents linked to any of these filings (compliance_item_documents).

    Used by marketplace to decide which documents a CA may open (MA14).
    """
    stmt = (
        select(ComplianceItemDocument.document_id)
        .join(Document, ComplianceItemDocument.document_id == Document.id)
        .where(
            ComplianceItemDocument.compliance_item_id.in_(filing_ids),
        )
    )
    return set(db.session.scalars(stmt))


# --- The vault (DO2 to DO7) -----------------------------------------------------------


def get_document(document_id) -> Document:
    """A document. 404 DOCUMENT_NOT_FOUND."""
    document = db.session.get(Document, document_id) if document_id else None
    if document is None:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "This document was not found.")
    return document


def _own_document(business, document_id) -> Document:
    """One live document of this business's owner. 404 DOCUMENT_NOT_FOUND for anyone else's."""
    document = get_document(document_id)
    if document.owner_id != business.user_id:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "This document was not found.")
    return document


def _filing_name(filing) -> str:
    """e.g. "GSTR-3B (Q1 2026-27)", for messages."""
    return compliance.filing_name(filing)


def _open_filing(business, item_id):
    """A live filing of this business whose documents may still change.

    404 FILING_NOT_FOUND for anyone else's; 409 FILING_LOCKED once it is filed.
    """
    filing = compliance.get_filings_by_ids([item_id]).get(item_id)
    if filing is None or filing.business_id != business.id:
        raise ApiError(404, "FILING_NOT_FOUND", "This filing was not found.")
    if filing.status in compliance.DONE_STATUSES:
        raise ApiError(
            409, "FILING_LOCKED", "This filing is filed, so its documents can no longer change."
        )
    return filing


def _check_key(filing, checklist_key: str) -> None:
    """422 UNKNOWN_CHECKLIST_KEY unless the key is "general" or in the form's checklist."""
    if checklist_key != GENERAL_KEY and checklist_key not in compliance.checklist_keys(
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
        compliance.tick_checklist_entry(filing, checklist_key)


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
    acknowledged = compliance.filings_by_acknowledgement(document_ids)
    filings = compliance.get_filings_by_ids({link.compliance_item_id for link in links})

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
            "type_warning": type_warning(document),
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
        Document.owner_id == business.user_id
    )
    if fy is not None:
        stmt = stmt.where(Document.fy == fy)
    if doc_type is not None:
        stmt = stmt.where(Document.doc_type == doc_type)
    if compliance_item_id is not None:
        linked = select(ComplianceItemDocument.document_id).where(
            ComplianceItemDocument.compliance_item_id == compliance_item_id
        )
        filing = compliance.get_filings_by_ids([compliance_item_id]).get(compliance_item_id)
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
    document = get_document(document_id)
    allowed = document.owner_id == user.id
    if not allowed and user.role == UserRole.CA:
        ca_profile_id = marketplace.own_profile_id(user)
        allowed = ca_profile_id is not None and marketplace.ca_can_access_document(
            ca_profile_id, document.id
        )
    if not allowed:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "This document was not found.")
    log.info("Document %s opened by user %s", document.id, user.id)
    return document, decrypt_bytes(document.content)


def delete_document(business, document_id) -> None:
    """Delete one of the business's documents with its links (DO5).

    409 DOCUMENT_IN_USE when it is a filing's acknowledgement or linked to a filed
    filing: it is the proof of that filing.
    """
    document = _own_document(business, document_id)
    acknowledged = compliance.filings_by_acknowledgement([document.id]).get(document.id)
    if acknowledged is not None:
        raise ApiError(
            409,
            "DOCUMENT_IN_USE",
            f"This is the acknowledgement of {_filing_name(acknowledged)}. "
            'Undo "mark as filed" on that filing to remove it.',
        )
    links = _links_of([document.id])
    filings = compliance.get_filings_by_ids({link.compliance_item_id for link in links})
    for filing in filings.values():
        if filing.status in compliance.DONE_STATUSES:
            raise ApiError(
                409,
                "DOCUMENT_IN_USE",
                f"This document is proof for {_filing_name(filing)}, which is filed, "
                "so it cannot be deleted.",
            )
    remove_document(document.id)
    db.session.commit()
    log.info("Document %s deleted", document.id)


def link_document(business, user: User, document_id, item_id, checklist_key: str) -> dict:
    """Link one of the business's documents to one of its filings (DO6). Linking it twice
    changes nothing. A checklist key (not "general") is ticked.

    404 DOCUMENT_NOT_FOUND, FILING_NOT_FOUND; 409 FILING_LOCKED; 422 UNKNOWN_CHECKLIST_KEY.
    """
    document = attach_document(business, user, document_id, item_id, checklist_key)
    db.session.commit()
    return _describe([document])[0]


def attach_document(business, user: User, document_id, item_id, checklist_key: str) -> Document:
    """link_document without the commit (ca_workspace fulfils a document request with it).

    404 DOCUMENT_NOT_FOUND, FILING_NOT_FOUND; 409 FILING_LOCKED; 422 UNKNOWN_CHECKLIST_KEY.
    """
    document = _own_document(business, document_id)
    filing = _open_filing(business, item_id)
    _check_key(filing, checklist_key)
    _link(filing, document, checklist_key, user)
    return document


def documents_by_filing(filings) -> dict:
    """{filing id: [{document_id, original_filename, doc_type, size_bytes, created_at,
    checklist_key}]}: the live files linked to each filing, then its acknowledgement
    (checklist_key "acknowledgement"). For the CA's client workspace (CW3)."""
    result = {filing.id: [] for filing in filings}
    stmt = (
        select(ComplianceItemDocument, Document)
        .join(Document, ComplianceItemDocument.document_id == Document.id)
        .where(
            ComplianceItemDocument.compliance_item_id.in_(list(result)),
        )
        .order_by(Document.created_at)
    )
    rows = [
        (link.compliance_item_id, link.checklist_key, doc) for link, doc in db.session.execute(stmt)
    ]
    for filing in filings:
        if filing.acknowledgement_document_id is not None:
            document = db.session.get(Document, filing.acknowledgement_document_id)
            if document is not None:
                rows.append((filing.id, ACKNOWLEDGEMENT_KEY, document))
    for filing_id, checklist_key, document in rows:
        result[filing_id].append(
            {
                "document_id": document.id,
                "original_filename": document.original_filename,
                "doc_type": document.doc_type,
                "size_bytes": document.size_bytes,
                "created_at": document.created_at,
                "checklist_key": checklist_key,
            }
        )
    return result


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


# --- Routes ------------------------------------------------------------------------------


blp = Blueprint(
    "documents", __name__, description="Document vault: upload, list, download, link to filings"
)


@blp.route("/documents", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(DocumentUploadFormSchema, location="form")
@blp.arguments(DocumentUploadFileSchema, location="files")
@blp.response(201, DocumentSchema)
@blp.alt_response(400, schema=ErrorSchema, description="FILE_EMPTY, FILE_TYPE_NOT_ALLOWED, ...")
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND, FILING_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="FILING_LOCKED")
def upload_document_view(form, files):
    return upload_document(
        current_business(),
        current_user(),
        files["file"],
        form["doc_type"],
        fy=form["fy"],
        period_label=form["period_label"],
        item_id=form["compliance_item_id"],
        checklist_key=form["checklist_key"],
    )


@blp.route("/documents", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(DocumentListArgsSchema, location="query")
@blp.response(200, DocumentPageSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND")
def list_documents_view(args):
    return list_documents(
        current_business(),
        args["page"],
        args["page_size"],
        fy=args["fy"],
        doc_type=args["doc_type"],
        compliance_item_id=args["compliance_item_id"],
    )


@blp.route("/documents/<uuid:document_id>/file", methods=["GET"])
@roles_required(UserRole.BUSINESS, UserRole.CA)
@blp.response(200, description="The file (PDF, JPG or PNG)")
@blp.alt_response(404, schema=ErrorSchema, description="DOCUMENT_NOT_FOUND")
def get_document_file_view(document_id):
    document, data = get_document_file(current_user(), document_id)
    return send_file(
        io.BytesIO(data), mimetype=document.mime_type, download_name=document.original_filename
    )


@blp.route("/documents/<uuid:document_id>", methods=["DELETE"])
@roles_required(UserRole.BUSINESS)
@blp.response(204)
@blp.alt_response(404, schema=ErrorSchema, description="DOCUMENT_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="DOCUMENT_IN_USE")
def delete_document_view(document_id):
    delete_document(current_business(), document_id)


@blp.route("/documents/<uuid:document_id>/links", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(DocumentLinkCreateSchema)
@blp.response(200, DocumentSchema)
@blp.alt_response(404, schema=ErrorSchema, description="DOCUMENT_NOT_FOUND, FILING_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="FILING_LOCKED")
@blp.alt_response(422, schema=ErrorSchema, description="UNKNOWN_CHECKLIST_KEY")
def link_document_view(data, document_id):
    return link_document(
        current_business(),
        current_user(),
        document_id,
        data["compliance_item_id"],
        data["checklist_key"],
    )


@blp.route("/documents/links/<uuid:link_id>", methods=["DELETE"])
@roles_required(UserRole.BUSINESS)
@blp.response(204)
@blp.alt_response(404, schema=ErrorSchema, description="LINK_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="FILING_LOCKED")
def unlink_document_view(link_id):
    unlink_document(current_business(), link_id)
