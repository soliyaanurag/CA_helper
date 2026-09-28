"""HTTP routes for ca workspace: /api/v1/ca-workspace/...

    GET  /ca-workspace/dashboard                        welcome text (CA home)
    GET  /ca-workspace/clients                          my clients, most urgent first (CW2, CW6)
    GET  /ca-workspace/clients/<id>                     one client's workspace (CW3)
    POST /ca-workspace/clients/<id>/document-requests   ask for a document (CW4)
    POST /ca-workspace/clients/<id>/filings/<item_id>/mark-filed   the CA filed it (CW5)
    GET  /ca-workspace/batches                          engaged filings by form + due date (CW7)
    POST /ca-workspace/document-requests/<id>/cancel    the CA takes a request back
    GET  /ca-workspace/document-requests                the business's open requests (its to-dos)
    POST /ca-workspace/document-requests/<id>/fulfil    the business answers with a document

Every CA route that names a business starts with require_ca_access(business_id)
(404 unless an ACTIVE engagement, CLAUDE.md rule 5).
Routes stay thin: parse input (app/schemas/), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from app.errors import ErrorSchema
from app.models.enums import UserRole
from app.schemas.ca_workspace import (
    BatchSchema,
    BusinessDocumentRequestSchema,
    CaClientDetailSchema,
    CaClientSchema,
    CaDashboardSchema,
    CaMarkFiledResultSchema,
    DocumentRequestArgsSchema,
    DocumentRequestCreateSchema,
    DocumentRequestSchema,
    FulfilSchema,
)
from app.schemas.compliance import MarkFiledFileSchema, MarkFiledFormSchema
from app.services import ca_workspace_service
from app.utils.decorators import (
    current_business,
    current_user,
    require_ca_access,
    roles_required,
)

blp = Blueprint(
    "ca_workspace", __name__, description="CA multi-client dashboard and client workspace"
)


@blp.route("/ca-workspace/dashboard")
class CaDashboard(MethodView):
    @roles_required(UserRole.CA)
    @blp.response(200, CaDashboardSchema)
    def get(self):
        return ca_workspace_service.get_dashboard(current_user())


@blp.route("/ca-workspace/clients", methods=["GET"])
@roles_required(UserRole.CA)
@blp.response(200, CaClientSchema(many=True))
@blp.alt_response(404, schema=ErrorSchema, description="CA_PROFILE_NOT_FOUND")
def list_clients():
    return ca_workspace_service.list_clients(current_user())


@blp.route("/ca-workspace/clients/<uuid:business_id>", methods=["GET"])
@roles_required(UserRole.CA)
@blp.response(200, CaClientDetailSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND")
def get_client(business_id):
    require_ca_access(business_id)
    return ca_workspace_service.get_client(current_user(), business_id)


@blp.route("/ca-workspace/clients/<uuid:business_id>/document-requests", methods=["POST"])
@roles_required(UserRole.CA)
@blp.arguments(DocumentRequestCreateSchema)
@blp.response(201, DocumentRequestSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND, FILING_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="FILING_LOCKED")
@blp.alt_response(422, schema=ErrorSchema, description="UNKNOWN_CHECKLIST_KEY")
def create_document_request(data, business_id):
    require_ca_access(business_id)
    return ca_workspace_service.create_document_request(
        current_user(),
        business_id,
        data["compliance_item_id"],
        data["checklist_key"],
        data["message"],
    )


@blp.route(
    "/ca-workspace/clients/<uuid:business_id>/filings/<uuid:item_id>/mark-filed", methods=["POST"]
)
@roles_required(UserRole.CA)
@blp.arguments(MarkFiledFormSchema, location="form")
@blp.arguments(MarkFiledFileSchema, location="files")
@blp.response(200, CaMarkFiledResultSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND, FILING_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="ALREADY_FILED, FILING_NOT_WITH_CA")
def mark_filed(form, files, business_id, item_id):
    require_ca_access(business_id)
    return ca_workspace_service.mark_filed_for_client(
        current_user(), business_id, item_id, form["acknowledgement_no"], files["file"]
    )


@blp.route("/ca-workspace/batches", methods=["GET"])
@roles_required(UserRole.CA)
@blp.response(200, BatchSchema(many=True))
@blp.alt_response(404, schema=ErrorSchema, description="CA_PROFILE_NOT_FOUND")
def list_batches():
    return ca_workspace_service.list_batches(current_user())


@blp.route("/ca-workspace/document-requests/<uuid:request_id>/cancel", methods=["POST"])
@roles_required(UserRole.CA)
@blp.response(200, DocumentRequestSchema)
@blp.alt_response(404, schema=ErrorSchema, description="REQUEST_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="REQUEST_NOT_OPEN")
def cancel_document_request(request_id):
    return ca_workspace_service.cancel_document_request(current_user(), request_id)


@blp.route("/ca-workspace/document-requests", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(DocumentRequestArgsSchema, location="query")
@blp.response(200, BusinessDocumentRequestSchema(many=True))
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND")
def list_business_requests(args):
    return ca_workspace_service.list_business_requests(
        current_business(), args["compliance_item_id"]
    )


@blp.route("/ca-workspace/document-requests/<uuid:request_id>/fulfil", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(FulfilSchema)
@blp.response(200, DocumentRequestSchema)
@blp.alt_response(404, schema=ErrorSchema, description="REQUEST_NOT_FOUND, DOCUMENT_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="REQUEST_NOT_OPEN, FILING_LOCKED")
def fulfil_document_request(data, request_id):
    return ca_workspace_service.fulfil_document_request(
        current_business(), current_user(), request_id, data["document_id"]
    )
