"""Request and response shapes for /api/v1/ca-workspace/...

Business logic for the CA's multi-client dashboard and client workspace.

get_dashboard(user) -> dict                               welcome text for the CA home page
list_clients(user, today) -> list                         clients by urgency (CW2, CW6)
get_client(user, business_id) -> dict                     one client's workspace (CW3)
list_batches(user, today) -> list                         engaged filings by form + due date (CW7)
create_document_request(user, business_id, ...) -> dict   ask the client for a document (CW4)
cancel_document_request(user, request_id) -> dict         the CA takes the request back
list_business_requests(business, item_id) -> list         the business's open requests (its to-dos)
fulfil_document_request(business, user, id, doc_id)       the business answers with a file
mark_filed_for_client(user, business_id, item_id, ...)    the CA filed one filing (CW5)

A CA works only on the filings of their ACTIVE engagements (marketplace,
CLAUDE.md rule 5). Every route that names a business calls require_ca_access() first;
the service then keeps to active_work(), so a CA with two clients, or a business with
two CAs, never mixes them up.

Urgency (CW6): a simple weighted sum, each part with its reason, so the CA sees why a
client is flagged. The weights are the constants below; regulatory changes add points
through regulatory_points() (approved changes from the regulatory module).

HTTP routes for ca workspace: /api/v1/ca-workspace/...

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

import logging
from datetime import date

from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import fields, post_load, Schema, validate, ValidationError
from sqlalchemy import select

from app import alerts, compliance, documents, marketplace, onboarding, regulatory
from app.compliance import (
    FilingDetailItemSchema,
    MarkFiledFileSchema,
    MarkFiledFormSchema,
    TickedChecklistEntrySchema,
)
from app.models import (
    ComplianceStatus,
    db,
    DocumentRequest,
    DocumentRequestStatus,
    DocumentType,
    FormCode,
    NotificationType,
    today_in_india,
    User,
    UserRole,
    utcnow,
)
from app.onboarding import MyBusinessSchema
from app.utils import (
    ApiError,
    current_business,
    current_user,
    ErrorSchema,
    require_ca_access,
    roles_required,
)


# --- Request and response shapes ---------------------------------------------------------


class CaDashboardSchema(Schema):
    message = fields.String(required=True, metadata={"description": "Welcome text"})


class UrgencyReasonSchema(Schema):
    reason = fields.String(required=True, metadata={"description": 'e.g. "2 filing(s) overdue"'})
    points = fields.Integer(required=True)


class CaClientSchema(Schema):
    """One client in "My clients" (CW2), with its urgency (CW6)."""

    business_id = fields.UUID(required=True)
    business_name = fields.String(required=True)
    filing_count = fields.Integer(required=True, metadata={"description": "Engaged filings"})
    open_filing_count = fields.Integer(required=True, metadata={"description": "Not filed yet"})
    open_request_count = fields.Integer(required=True)
    next_deadline = fields.Date(allow_none=True)
    overdue_count = fields.Integer(required=True)
    missing_documents = fields.Integer(required=True)
    score = fields.Integer(required=True, metadata={"description": "Urgency: the sum of points"})
    reasons = fields.List(fields.Nested(UrgencyReasonSchema), required=True)


class DocumentRequestSchema(Schema):
    id = fields.UUID(required=True)
    compliance_item_id = fields.UUID(required=True)
    form_code = fields.String(validate=validate.OneOf(list(FormCode)), allow_none=True)
    period_label = fields.String(allow_none=True)
    checklist_key = fields.String(required=True, metadata={"description": 'or "general"'})
    message = fields.String(required=True)
    status = fields.String(validate=validate.OneOf(list(DocumentRequestStatus)), required=True)
    created_at = fields.DateTime(required=True)
    fulfilled_at = fields.DateTime(allow_none=True)
    document_id = fields.UUID(allow_none=True)


class BusinessDocumentRequestSchema(DocumentRequestSchema):
    ca_name = fields.String(required=True)


class ClientDocumentSchema(Schema):
    document_id = fields.UUID(required=True)
    original_filename = fields.String(required=True)
    doc_type = fields.String(validate=validate.OneOf(list(DocumentType)), required=True)
    size_bytes = fields.Integer(required=True)
    created_at = fields.DateTime(required=True)
    checklist_key = fields.String(
        required=True, metadata={"description": 'A checklist key, "general" or "acknowledgement"'}
    )


class ClientFilingSchema(Schema):
    filing = fields.Nested(FilingDetailItemSchema, required=True)
    checklist = fields.List(fields.Nested(TickedChecklistEntrySchema), required=True)
    documents = fields.List(fields.Nested(ClientDocumentSchema), required=True)
    open_requests = fields.List(fields.Nested(DocumentRequestSchema), required=True)


class CaClientDetailSchema(MyBusinessSchema):
    """GET /ca-workspace/clients/<id> (CW3): the business, its profile and the CA's filings."""

    filings = fields.List(fields.Nested(ClientFilingSchema), required=True)


class BatchFilingSchema(Schema):
    business_id = fields.UUID(required=True)
    business_name = fields.String(required=True)
    compliance_item_id = fields.UUID(required=True)
    period_label = fields.String(required=True)
    status = fields.String(validate=validate.OneOf(list(ComplianceStatus)), required=True)
    required_total = fields.Integer(required=True)
    required_ready = fields.Integer(required=True)
    missing = fields.List(fields.String(), required=True)
    ready = fields.Boolean(required=True)


class BatchSchema(Schema):
    """One form due on one day across clients (CW7)."""

    form_code = fields.String(validate=validate.OneOf(list(FormCode)), required=True)
    due_date = fields.Date(required=True)
    ready_count = fields.Integer(required=True)
    filings = fields.List(fields.Nested(BatchFilingSchema), required=True)


class DocumentRequestCreateSchema(Schema):
    """POST /ca-workspace/clients/<id>/document-requests (CW4)."""

    compliance_item_id = fields.UUID(required=True)
    checklist_key = fields.String(load_default="general", validate=validate.Length(1, 50))
    message = fields.String(required=True, validate=validate.Length(1, 1000))

    @post_load
    def _clean(self, data: dict, **kwargs) -> dict:
        data["message"] = data["message"].strip()
        if not data["message"]:
            raise ValidationError("Write what you need.", "message")
        return data


class DocumentRequestArgsSchema(Schema):
    compliance_item_id = fields.UUID(load_default=None)


class FulfilSchema(Schema):
    """POST /ca-workspace/document-requests/<id>/fulfil."""

    document_id = fields.UUID(required=True)


class CaMarkFiledResultSchema(Schema):
    compliance_item_id = fields.UUID(required=True)
    status = fields.String(validate=validate.OneOf(list(ComplianceStatus)), required=True)
    acknowledgement_no = fields.String(allow_none=True)
    engagement_completed = fields.Boolean(
        required=True, metadata={"description": "True when this was the engagement's last filing"}
    )


# --- Logic -------------------------------------------------------------------------------


log = logging.getLogger(__name__)

# Urgency weights (CW6).
POINTS_PER_OVERDUE_FILING = 40
POINTS_DUE_WITHIN_3_DAYS = 25  # the next deadline is 0 to 3 days away
POINTS_DUE_WITHIN_7_DAYS = 10  # 4 to 7 days away
POINTS_PER_MISSING_DOCUMENT = 5  # a required checklist entry not ticked
POINTS_PER_OPEN_REQUEST = 3  # a document asked for and not received yet
POINTS_PER_REGULATORY_CHANGE = 15  # an approved rule change affected this client (30 days)


def get_dashboard(user: User) -> dict:
    """Data for the CA's home page: a welcome message."""
    return {"message": f"Welcome, {user.full_name}"}


def _ca_profile_id(user: User):
    """The CA's profile id. 404 CA_PROFILE_NOT_FOUND before the profile is saved."""
    ca_profile_id = marketplace.own_profile_id(user)
    if ca_profile_id is None:
        raise ApiError(404, "CA_PROFILE_NOT_FOUND", "Save your CA profile first.")
    return ca_profile_id


def _work_by_client(ca_profile_id) -> dict:
    """{business id: {filing id: engagement id}} for the CA's ACTIVE engagements."""
    clients = {}
    for engagement_id, business_id, item_id in marketplace.active_work(ca_profile_id):
        clients.setdefault(business_id, {})[item_id] = engagement_id
    return clients


def _open_requests(engagement_ids, item_ids=None) -> list[DocumentRequest]:
    """The open document requests of these engagements (optionally only for some filings)."""
    if len(engagement_ids) == 0:
        return []
    stmt = select(DocumentRequest).where(
        DocumentRequest.engagement_id.in_(engagement_ids),
        DocumentRequest.status == DocumentRequestStatus.OPEN,
    )
    if item_ids is not None:
        stmt = stmt.where(DocumentRequest.compliance_item_id.in_(item_ids))
    return list(db.session.scalars(stmt.order_by(DocumentRequest.created_at)))


def regulatory_points(business_id) -> list[dict]:
    """Extra urgency from approved regulatory changes that affected this business in the
    last 30 days (regulatory module, RE5): [{reason, points}], one per change."""
    points = []
    for change in regulatory.active_changes_for(business_id):
        forms = regulatory.forms_text(change.form_codes)
        points.append(
            {"reason": f"Regulatory update ({forms})", "points": POINTS_PER_REGULATORY_CHANGE}
        )
    return points


def _urgency(filings, open_request_count: int, business_id, today: date) -> dict:
    """{score, reasons: [{reason, points}], next_deadline, overdue_count, missing_documents}
    for one client's engaged filings that are not filed yet."""
    overdue = [filing for filing in filings if filing.due_date < today]
    upcoming = sorted(
        (filing for filing in filings if filing.due_date >= today), key=lambda f: f.due_date
    )
    missing = 0
    for filing in filings:
        missing += len(compliance.checklist_progress(filing)["missing"])

    reasons = []
    if overdue:
        reasons.append(
            {
                "reason": f"{len(overdue)} filing(s) overdue",
                "points": len(overdue) * POINTS_PER_OVERDUE_FILING,
            }
        )
    next_deadline = upcoming[0].due_date if upcoming else None
    if next_deadline is not None:
        days = (next_deadline - today).days
        if days <= 3:
            reasons.append(
                {"reason": f"Next deadline in {days} day(s)", "points": POINTS_DUE_WITHIN_3_DAYS}
            )
        elif days <= 7:
            reasons.append(
                {"reason": f"Next deadline in {days} days", "points": POINTS_DUE_WITHIN_7_DAYS}
            )
    if missing:
        reasons.append(
            {
                "reason": f"{missing} required document(s) not ready",
                "points": missing * POINTS_PER_MISSING_DOCUMENT,
            }
        )
    if open_request_count:
        reasons.append(
            {
                "reason": f"{open_request_count} document request(s) not answered",
                "points": open_request_count * POINTS_PER_OPEN_REQUEST,
            }
        )
    reasons.extend(regulatory_points(business_id))
    return {
        "score": sum(reason["points"] for reason in reasons),
        "reasons": reasons,
        "next_deadline": next_deadline,
        "overdue_count": len(overdue),
        "missing_documents": missing,
    }


def list_clients(user: User, today: date | None = None) -> list[dict]:
    """The CA's clients (ACTIVE engagements), most urgent first (CW2, CW6)."""
    today = today or today_in_india()
    clients = _work_by_client(_ca_profile_id(user))
    rows = []
    for business_id, work in clients.items():
        business = onboarding.get_business(business_id)
        filings = compliance.get_filings_by_ids(list(work)).values()
        not_filed = [f for f in filings if f.status not in compliance.DONE_STATUSES]
        open_requests = _open_requests(set(work.values()), list(work))
        rows.append(
            {
                "business_id": business_id,
                "business_name": business.legal_name,
                "filing_count": len(work),
                "open_filing_count": len(not_filed),
                "open_request_count": len(open_requests),
                **_urgency(not_filed, len(open_requests), business_id, today),
            }
        )
    rows.sort(key=lambda row: (-row["score"], row["business_name"]))
    return rows


def _request_details(request: DocumentRequest, filing=None) -> dict:
    filing = filing or compliance.get_filings_by_ids([request.compliance_item_id]).get(
        request.compliance_item_id
    )
    return {
        "id": request.id,
        "compliance_item_id": request.compliance_item_id,
        "form_code": filing.form_code if filing else None,
        "period_label": filing.period_label if filing else None,
        "checklist_key": request.checklist_key,
        "message": request.message,
        "status": request.status,
        "created_at": request.created_at,
        "fulfilled_at": request.fulfilled_at,
        "document_id": request.document_id,
    }


def get_client(user: User, business_id) -> dict:
    """One client's workspace (CW3): the business and its profile, and the filings of the
    CA's active engagements with their checklist, documents and document requests.

    The route has checked the CA's active access (require_ca_access).
    """
    work = _work_by_client(_ca_profile_id(user)).get(business_id, {})
    business = onboarding.get_business(business_id)
    filings = sorted(
        compliance.get_filings_by_ids(list(work)).values(), key=lambda f: f.due_date
    )
    files_by_filing = documents.documents_by_filing(filings)
    requests = {}
    for request in _open_requests(set(work.values()), list(work)):
        requests.setdefault(request.compliance_item_id, []).append(request)

    rows = []
    for filing in filings:
        rows.append(
            {
                "filing": filing,
                "checklist": compliance.checklist_with_ticks(filing),
                "documents": files_by_filing[filing.id],
                "open_requests": [
                    _request_details(request, filing) for request in requests.get(filing.id, [])
                ],
            }
        )
    return {**onboarding.get_my_business(business), "filings": rows}


def list_batches(user: User, today: date | None = None) -> list[dict]:
    """The CA's engaged, not-filed filings across clients, grouped by form and due date,
    soonest first, with each client's document readiness (CW7)."""
    groups = {}
    for business_id, work in _work_by_client(_ca_profile_id(user)).items():
        business = onboarding.get_business(business_id)
        for filing in compliance.get_filings_by_ids(list(work)).values():
            if filing.status in compliance.DONE_STATUSES:
                continue
            progress = compliance.checklist_progress(filing)
            groups.setdefault((filing.due_date, filing.form_code), []).append(
                {
                    "business_id": business_id,
                    "business_name": business.legal_name,
                    "compliance_item_id": filing.id,
                    "period_label": filing.period_label,
                    "status": filing.status,
                    **progress,
                    "ready": len(progress["missing"]) == 0,
                }
            )
    batches = []
    for (due_date, form_code), filings in sorted(groups.items()):
        filings.sort(key=lambda row: row["business_name"])
        batches.append(
            {
                "form_code": form_code,
                "due_date": due_date,
                "ready_count": sum(1 for row in filings if row["ready"]),
                "filings": filings,
            }
        )
    return batches


def _engagement_of(user: User, business_id, item_id):
    """The CA's ACTIVE engagement that includes this filing of this client.
    404 FILING_NOT_FOUND if the filing is not in the CA's active work."""
    work = _work_by_client(_ca_profile_id(user)).get(business_id, {})
    if item_id not in work:
        raise ApiError(404, "FILING_NOT_FOUND", "This filing is not in your active work.")
    return work[item_id]


def create_document_request(user: User, business_id, item_id, checklist_key, message) -> dict:
    """The CA asks the client for a document for one engaged filing (CW4). The business
    owner gets a tray entry and an email (type document_request).

    404 FILING_NOT_FOUND; 422 UNKNOWN_CHECKLIST_KEY; 409 FILING_LOCKED once filed.
    """
    engagement_id = _engagement_of(user, business_id, item_id)
    business = onboarding.get_business(business_id)
    filing = compliance.get_filings_by_ids([item_id])[item_id]
    if filing.status in compliance.DONE_STATUSES:
        raise ApiError(409, "FILING_LOCKED", "This filing is already filed.")
    if checklist_key != documents.GENERAL_KEY and checklist_key not in (
        compliance.checklist_keys(filing.form_code)
    ):
        raise ApiError(422, "UNKNOWN_CHECKLIST_KEY", "This checklist entry does not exist.")

    request = DocumentRequest(
        engagement_id=engagement_id,
        compliance_item_id=item_id,
        checklist_key=checklist_key,
        message=message,
    )
    db.session.add(request)
    owner = db.session.get(User, business.user_id)
    title = f"Your CA asked for a document for {compliance.filing_name(filing)}"
    body = f"{user.full_name}: {message}"
    alerts.notify(
        owner, NotificationType.DOCUMENT_REQUEST, title, body, f"/business/compliance/{filing.id}"
    )
    db.session.commit()
    alerts.email_notice(owner, title, body)
    log.info("Document request %s created for filing %s", request.id, filing.id)
    return _request_details(request, filing)


def cancel_document_request(user: User, request_id) -> dict:
    """The CA takes an open request back. 404 REQUEST_NOT_FOUND (not theirs, or not active
    work any more); 409 REQUEST_NOT_OPEN."""
    request = db.session.get(DocumentRequest, request_id)
    engagements = {row[0] for row in marketplace.active_work(_ca_profile_id(user))}
    if request is None or request.engagement_id not in engagements:
        raise ApiError(404, "REQUEST_NOT_FOUND", "This document request was not found.")
    if request.status != DocumentRequestStatus.OPEN:
        raise ApiError(409, "REQUEST_NOT_OPEN", "This request is no longer open.")
    request.status = DocumentRequestStatus.CANCELLED
    db.session.commit()
    return _request_details(request)


def list_business_requests(business, item_id=None) -> list[dict]:
    """The business's open document requests from its CAs (active engagements), oldest
    first; optionally for one filing. Each has the CA's name."""
    cas = marketplace.active_cas_of_business(business.id)
    item_ids = [item_id] if item_id is not None else None
    rows = []
    for request in _open_requests(set(cas), item_ids):
        rows.append({**_request_details(request), "ca_name": cas[request.engagement_id].full_name})
    return rows


def fulfil_document_request(business, user: User, request_id, document_id) -> dict:
    """The business answers a request with one of its documents (uploaded first, or from
    the vault): the file is linked to the filing under the requested checklist key (which
    ticks it), and the CA gets a tray entry and an email.

    404 REQUEST_NOT_FOUND, DOCUMENT_NOT_FOUND; 409 REQUEST_NOT_OPEN, FILING_LOCKED.
    """
    request = db.session.get(DocumentRequest, request_id)
    cas = marketplace.active_cas_of_business(business.id)
    if request is None or request.engagement_id not in cas:
        raise ApiError(404, "REQUEST_NOT_FOUND", "This document request was not found.")
    if request.status != DocumentRequestStatus.OPEN:
        raise ApiError(409, "REQUEST_NOT_OPEN", "This request is no longer open.")
    documents.attach_document(
        business, user, document_id, request.compliance_item_id, request.checklist_key
    )
    request.status = DocumentRequestStatus.FULFILLED
    request.fulfilled_at = utcnow()
    request.document_id = document_id
    filing = compliance.get_filings_by_ids([request.compliance_item_id])[
        request.compliance_item_id
    ]
    ca_user = cas[request.engagement_id]
    title = f"{business.legal_name} sent the document you asked for"
    body = f"For {compliance.filing_name(filing)}: {request.message}"
    alerts.notify(
        ca_user, NotificationType.DOCUMENT_REQUEST, title, body, f"/ca/clients/{business.id}"
    )
    db.session.commit()
    alerts.email_notice(ca_user, title, body)
    log.info("Document request %s fulfilled", request.id)
    return _request_details(request, filing)


def mark_filed_for_client(
    user: User, business_id, item_id, acknowledgement_no=None, upload=None
) -> dict:
    """The CA filed one engaged filing (CW5), with an optional ARN and acknowledgement.
    The business is told; when it was the engagement's last filing, the engagement is
    completed. Returns {compliance_item_id, status, acknowledgement_no, engagement_completed}.

    404 FILING_NOT_FOUND; 409 ALREADY_FILED, FILING_NOT_WITH_CA; storage errors.
    """
    engagement_id = _engagement_of(user, business_id, item_id)
    business = onboarding.get_business(business_id)
    filing = compliance.mark_filed_by_ca(
        business, user, item_id, acknowledgement_no, upload
    )
    # Requests for a filed filing can no longer be answered.
    for request in _open_requests({engagement_id}, [item_id]):
        request.status = DocumentRequestStatus.CANCELLED
    owner = db.session.get(User, business.user_id)
    title = f"Your CA filed {compliance.filing_name(filing)}"
    body = f"{user.full_name} marked it as filed"
    if filing.acknowledgement_no:
        body += f" (acknowledgement number {filing.acknowledgement_no})."
    else:
        body += "."
    alerts.notify(
        owner, NotificationType.ENGAGEMENT_UPDATE, title, body, f"/business/compliance/{filing.id}"
    )
    completed = marketplace.complete_if_all_filed(engagement_id)
    db.session.commit()
    alerts.email_notice(owner, title, body)
    return {
        "compliance_item_id": filing.id,
        "status": filing.status,
        "acknowledgement_no": filing.acknowledgement_no,
        "engagement_completed": completed,
    }


# --- Routes ------------------------------------------------------------------------------


blp = Blueprint(
    "ca_workspace", __name__, description="CA multi-client dashboard and client workspace"
)


@blp.route("/ca-workspace/dashboard")
class CaDashboard(MethodView):
    @roles_required(UserRole.CA)
    @blp.response(200, CaDashboardSchema)
    def get(self):
        return get_dashboard(current_user())


@blp.route("/ca-workspace/clients", methods=["GET"])
@roles_required(UserRole.CA)
@blp.response(200, CaClientSchema(many=True))
@blp.alt_response(404, schema=ErrorSchema, description="CA_PROFILE_NOT_FOUND")
def list_clients_view():
    return list_clients(current_user())


@blp.route("/ca-workspace/clients/<uuid:business_id>", methods=["GET"])
@roles_required(UserRole.CA)
@blp.response(200, CaClientDetailSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND")
def get_client_view(business_id):
    require_ca_access(business_id)
    return get_client(current_user(), business_id)


@blp.route("/ca-workspace/clients/<uuid:business_id>/document-requests", methods=["POST"])
@roles_required(UserRole.CA)
@blp.arguments(DocumentRequestCreateSchema)
@blp.response(201, DocumentRequestSchema)
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND, FILING_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="FILING_LOCKED")
@blp.alt_response(422, schema=ErrorSchema, description="UNKNOWN_CHECKLIST_KEY")
def create_document_request_view(data, business_id):
    require_ca_access(business_id)
    return create_document_request(
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
    return mark_filed_for_client(
        current_user(), business_id, item_id, form["acknowledgement_no"], files["file"]
    )


@blp.route("/ca-workspace/batches", methods=["GET"])
@roles_required(UserRole.CA)
@blp.response(200, BatchSchema(many=True))
@blp.alt_response(404, schema=ErrorSchema, description="CA_PROFILE_NOT_FOUND")
def list_batches_view():
    return list_batches(current_user())


@blp.route("/ca-workspace/document-requests/<uuid:request_id>/cancel", methods=["POST"])
@roles_required(UserRole.CA)
@blp.response(200, DocumentRequestSchema)
@blp.alt_response(404, schema=ErrorSchema, description="REQUEST_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="REQUEST_NOT_OPEN")
def cancel_document_request_view(request_id):
    return cancel_document_request(current_user(), request_id)


@blp.route("/ca-workspace/document-requests", methods=["GET"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(DocumentRequestArgsSchema, location="query")
@blp.response(200, BusinessDocumentRequestSchema(many=True))
@blp.alt_response(404, schema=ErrorSchema, description="BUSINESS_NOT_FOUND")
def list_business_requests_view(args):
    return list_business_requests(
        current_business(), args["compliance_item_id"]
    )


@blp.route("/ca-workspace/document-requests/<uuid:request_id>/fulfil", methods=["POST"])
@roles_required(UserRole.BUSINESS)
@blp.arguments(FulfilSchema)
@blp.response(200, DocumentRequestSchema)
@blp.alt_response(404, schema=ErrorSchema, description="REQUEST_NOT_FOUND, DOCUMENT_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="REQUEST_NOT_OPEN, FILING_LOCKED")
def fulfil_document_request_view(data, request_id):
    return fulfil_document_request(
        current_business(), current_user(), request_id, data["document_id"]
    )
