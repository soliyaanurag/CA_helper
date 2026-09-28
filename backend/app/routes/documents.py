"""HTTP routes for documents: /api/v1/documents/...

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

import io

from flask import send_file
from flask_smorest import Blueprint

from app.errors import ErrorSchema
from app.models.enums import UserRole
from app.schemas.documents import (
    DocumentLinkCreateSchema,
    DocumentListArgsSchema,
    DocumentPageSchema,
    DocumentSchema,
    DocumentUploadFileSchema,
    DocumentUploadFormSchema,
)
from app.services import documents_service
from app.utils.decorators import current_business, current_user, roles_required

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
def upload_document(form, files):
    return documents_service.upload_document(
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
def list_documents(args):
    return documents_service.list_documents(
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
def get_document_file(document_id):
    document, data = documents_service.get_document_file(current_user(), document_id)
    return send_file(
        io.BytesIO(data), mimetype=document.mime_type, download_name=document.original_filename
    )


@blp.route("/documents/<uuid:document_id>", methods=["DELETE"])
@roles_required(UserRole.BUSINESS)
@blp.response(204)
@blp.alt_response(404, schema=ErrorSchema, description="DOCUMENT_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="DOCUMENT_IN_USE")
def delete_document(document_id):
    documents_service.delete_document(current_business(), document_id)


@blp.route("/documents/<uuid:document_id>/links", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(DocumentLinkCreateSchema)
@blp.response(200, DocumentSchema)
@blp.alt_response(404, schema=ErrorSchema, description="DOCUMENT_NOT_FOUND, FILING_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="FILING_LOCKED")
@blp.alt_response(422, schema=ErrorSchema, description="UNKNOWN_CHECKLIST_KEY")
def link_document(data, document_id):
    return documents_service.link_document(
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
def unlink_document(link_id):
    documents_service.unlink_document(current_business(), link_id)
