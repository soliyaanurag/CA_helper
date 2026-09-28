"""HTTP routes for compliance: /api/v1/compliance/... (business role only).

    GET  /compliance/dashboard                   home page numbers (CO12)
    GET  /compliance/items                       the business's filings, soonest due first (CO4)
    GET  /compliance/items/<id>                  one filing's page (CO5)
    POST /compliance/items/<id>/path             file it myself / with a CA (CO8)
    POST /compliance/items/<id>/checklist        tick or untick a document (CO7)
    POST /compliance/items/<id>/mark-filed       filed it myself, with the acknowledgement (CO9)
    POST /compliance/items/<id>/unmark-filed     undo a mistaken "mark as filed"
    GET  /compliance/items/<id>/acknowledgement  the uploaded acknowledgement file
    GET  /compliance/forms/<form_code>           a form's explanation, instructions, checklist (CO6)

Routes stay thin: parse input (app/schemas/), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

import io

from flask import send_file
from flask_smorest import Blueprint

from app.errors import ErrorSchema
from app.models.enums import UserRole
from app.schemas.compliance import (
    ChecklistTickSchema,
    ChoosePathSchema,
    ComplianceDashboardSchema,
    ComplianceItemSchema,
    FilingDetailSchema,
    FormContentSchema,
    ItemListArgsSchema,
    MarkFiledFileSchema,
    MarkFiledFormSchema,
)
from app.services import compliance_service
from app.utils.decorators import (
    current_business,
    current_business_or_none,
    current_user,
    login_required,
    roles_required,
)

blp = Blueprint(
    "compliance",
    __name__,
    description="Obligations, compliance calendar, item pages and home dashboard",
)

NOT_FOUND = "BUSINESS_NOT_FOUND (register first), FILING_NOT_FOUND"


# The business home page: next deadline and counts (just the welcome before registering).
@blp.route("/compliance/dashboard", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, ComplianceDashboardSchema)
def get_dashboard():
    return compliance_service.get_dashboard(current_user(), current_business_or_none())


# The logged-in business sees its filings, optionally filtered.
@blp.route("/compliance/items", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(ItemListArgsSchema, location="query")
@blp.response(200, ComplianceItemSchema(many=True))
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND (register first)")
def list_items(filters):
    return compliance_service.list_filings(current_business(), **filters)


# One filing's page: dates, status, the form's texts, the checklist and the acknowledgement.
@blp.route("/compliance/items/<uuid:item_id>", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, FilingDetailSchema)
@blp.alt_response(404, schema=ErrorSchema, description=NOT_FOUND)
def get_item(item_id):
    return compliance_service.get_filing(current_business(), item_id)


# The business chooses: file it myself ("self") or with a CA ("ca").
@blp.route("/compliance/items/<uuid:item_id>/path", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(ChoosePathSchema)
@blp.response(200, FilingDetailSchema)
@blp.alt_response(409, schema=ErrorSchema, description="FILING_LOCKED (with a CA or filed)")
def choose_path(data, item_id):
    return compliance_service.choose_path(current_business(), item_id, data["path"])


# Tick or untick one document of the checklist; the status follows.
@blp.route("/compliance/items/<uuid:item_id>/checklist", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(ChecklistTickSchema)
@blp.response(200, FilingDetailSchema)
@blp.alt_response(422, schema=ErrorSchema, description="UNKNOWN_CHECKLIST_KEY")
def tick_checklist(data, item_id):
    return compliance_service.set_checklist_tick(
        current_business(), item_id, data["key"], data["ticked"]
    )


# The business filed it itself: optional ARN and acknowledgement file (multipart/form-data).
@blp.route("/compliance/items/<uuid:item_id>/mark-filed", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(MarkFiledFormSchema, location="form")
@blp.arguments(MarkFiledFileSchema, location="files")
@blp.response(200, FilingDetailSchema)
@blp.alt_response(409, schema=ErrorSchema, description="FILING_WITH_CA, ALREADY_FILED")
def mark_filed(form, files, item_id):
    return compliance_service.mark_filed(
        current_business(), current_user(), item_id, form["acknowledgement_no"], files["file"]
    )


# Undo a mistaken "mark as filed".
@blp.route("/compliance/items/<uuid:item_id>/unmark-filed", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, FilingDetailSchema)
@blp.alt_response(409, schema=ErrorSchema, description="NOT_SELF_FILED")
def unmark_filed(item_id):
    return compliance_service.unmark_filed(current_business(), item_id)


# The acknowledgement file the business uploaded.
@blp.route("/compliance/items/<uuid:item_id>/acknowledgement", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.response(200, description="The acknowledgement file (PDF, JPG or PNG)")
@blp.alt_response(404, schema=ErrorSchema, description="ACKNOWLEDGEMENT_MISSING")
def get_acknowledgement(item_id):
    document, data = compliance_service.get_acknowledgement(current_business(), item_id)
    return send_file(
        io.BytesIO(data), mimetype=document.mime_type, download_name=document.original_filename
    )


# A form's explanation, self-filing instructions and document checklist (any logged-in user).
@blp.route("/compliance/forms/<string:form_code>", methods=["GET"])
@login_required
@blp.response(200, FormContentSchema)
@blp.alt_response(404, schema=ErrorSchema, description="FORM_NOT_FOUND")
def get_form(form_code):
    return compliance_service.get_form_content(form_code)
