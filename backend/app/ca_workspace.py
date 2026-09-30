"""The CA's workspace: their clients sorted by urgency, one client's page, document
requests, marking a filing as filed, and batches of the same filing across clients.

A CA works only on the filings of their ACTIVE engagements. Every route that names a
business checks that first (require_ca_access), and the code keeps to active_work(), so a
CA with two clients, or a business with two CAs, never mixes them up.

Urgency is a simple weighted sum, each part with its reason, so the CA sees why a client
is flagged. The weights are the constants below.
"""

import logging
from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app import alerts, compliance, documents, marketplace, onboarding, regulatory
from app.models import (
    DocumentRequest,
    DocumentRequestStatus,
    NotificationType,
    User,
    UserRole,
    db,
    today_in_india,
    utcnow,
)
from app.utils import (
    MISSING,
    ApiError,
    current_business,
    current_user,
    iso,
    json_body,
    read_uuid,
    require_ca_access,
    roles_required,
    validation_error,
)

log = logging.getLogger(__name__)

bp = Blueprint("ca_workspace", __name__)

# Urgency weights (product weights, not legal values).
POINTS_PER_OVERDUE_FILING = 40
POINTS_DUE_WITHIN_3_DAYS = 25  # the next deadline is 0 to 3 days away
POINTS_DUE_WITHIN_7_DAYS = 10  # 4 to 7 days away
POINTS_PER_MISSING_DOCUMENT = 5  # a required checklist entry not ticked
POINTS_PER_OPEN_REQUEST = 3  # a document asked for and not received yet
POINTS_PER_REGULATORY_CHANGE = 15  # a rule change affected this client (30 days)


def request_to_dict(document_request: DocumentRequest, filing=None) -> dict:
    """One document request (the filing is looked up when not given)."""
    if filing is None:
        filing = compliance.get_filings_by_ids([document_request.compliance_item_id]).get(
            document_request.compliance_item_id
        )
    return {
        "id": str(document_request.id),
        "compliance_item_id": str(document_request.compliance_item_id),
        "form_code": filing.form_code if filing else None,
        "period_label": filing.period_label if filing else None,
        "checklist_key": document_request.checklist_key,
        "message": document_request.message,
        "status": document_request.status,
        "created_at": iso(document_request.created_at),
        "fulfilled_at": iso(document_request.fulfilled_at),
        "document_id": str(document_request.document_id) if document_request.document_id else None,
    }


def ca_profile_id_of(user: User):
    """The CA's profile id. 404 CA_PROFILE_NOT_FOUND before the profile is saved."""
    ca_profile_id = marketplace.own_profile_id(user)
    if ca_profile_id is None:
        raise ApiError(404, "CA_PROFILE_NOT_FOUND", "Save your CA profile first.")
    return ca_profile_id


def work_by_client(ca_profile_id) -> dict:
    """{business id: {filing id: engagement id}} for the CA's ACTIVE engagements."""
    clients = {}
    for engagement_id, business_id, item_id in marketplace.active_work(ca_profile_id):
        clients.setdefault(business_id, {})[item_id] = engagement_id
    return clients


def open_requests(engagement_ids, item_ids=None) -> list[DocumentRequest]:
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


def engagement_of(user: User, business_id, item_id):
    """The CA's ACTIVE engagement that includes this filing of this client.
    404 FILING_NOT_FOUND if the filing is not in the CA's active work."""
    work = work_by_client(ca_profile_id_of(user)).get(business_id, {})
    if item_id not in work:
        raise ApiError(404, "FILING_NOT_FOUND", "This filing is not in your active work.")
    return work[item_id]


# --- Urgency -----------------------------------------------------------------------------


def regulatory_points(business_id) -> list[dict]:
    """Extra urgency from regulatory changes that affected this business in the last 30
    days: [{reason, points}], one per change."""
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


# --- Routes for the CA -------------------------------------------------------------------


@bp.get("/ca-workspace/dashboard")
@roles_required(UserRole.CA)
def dashboard():
    return jsonify({"message": f"Welcome, {current_user().full_name}"})


@bp.get("/ca-workspace/clients")
@roles_required(UserRole.CA)
def list_clients():
    """The CA's clients (ACTIVE engagements), most urgent first."""
    today = today_in_india()
    rows = []
    for business_id, work in work_by_client(ca_profile_id_of(current_user())).items():
        business = onboarding.get_business(business_id)
        filings = compliance.get_filings_by_ids(list(work)).values()
        not_filed = [f for f in filings if f.status not in compliance.DONE_STATUSES]
        requests = open_requests(set(work.values()), list(work))
        urgency = _urgency(not_filed, len(requests), business_id, today)
        urgency["next_deadline"] = iso(urgency["next_deadline"])
        rows.append(
            {
                "business_id": str(business_id),
                "business_name": business.legal_name,
                "filing_count": len(work),
                "open_filing_count": len(not_filed),
                "open_request_count": len(requests),
                **urgency,
            }
        )
    rows.sort(key=lambda row: (-row["score"], row["business_name"]))
    return jsonify(rows)


@bp.get("/ca-workspace/clients/<uuid:business_id>")
@roles_required(UserRole.CA)
def get_client(business_id):
    """One client's page: the business and its profile, and the filings of the CA's active
    engagements with their checklist, documents and open document requests."""
    require_ca_access(business_id)
    work = work_by_client(ca_profile_id_of(current_user())).get(business_id, {})
    business = onboarding.get_business(business_id)
    filings = sorted(compliance.get_filings_by_ids(list(work)).values(), key=lambda f: f.due_date)
    files_by_filing = documents.documents_by_filing(filings)
    requests = {}
    for document_request in open_requests(set(work.values()), list(work)):
        requests.setdefault(document_request.compliance_item_id, []).append(document_request)

    page = onboarding.business_page(business)
    page["filings"] = []
    for filing in filings:
        page["filings"].append(
            {
                "filing": compliance.filing_detail_to_dict(filing),
                "checklist": compliance.checklist_with_ticks(filing),
                "documents": files_by_filing[filing.id],
                "open_requests": [
                    request_to_dict(item, filing) for item in requests.get(filing.id, [])
                ],
            }
        )
    return jsonify(page)


@bp.post("/ca-workspace/clients/<uuid:business_id>/document-requests")
@roles_required(UserRole.CA)
def create_document_request(business_id):
    """The CA asks the client for a document for one engaged filing; the business owner
    gets a tray entry and an email."""
    data = json_body()
    errors = {}
    item_id = data.get("compliance_item_id")
    if item_id is None:
        errors["compliance_item_id"] = [MISSING]
    elif read_uuid(item_id) is None:
        errors["compliance_item_id"] = ["Not a valid UUID."]
    checklist_key = data.get("checklist_key", documents.GENERAL_KEY)
    if not isinstance(checklist_key, str) or not 1 <= len(checklist_key) <= 50:
        errors["checklist_key"] = ["Length must be between 1 and 50."]
    message = data.get("message")
    if message is None:
        errors["message"] = [MISSING]
    elif not isinstance(message, str) or not 1 <= len(message) <= 1000:
        errors["message"] = ["Length must be between 1 and 1000."]
    elif not message.strip():
        errors["message"] = ["Write what you need."]
    if errors:
        raise validation_error(errors)

    require_ca_access(business_id)
    user = current_user()
    item_id = read_uuid(item_id)
    engagement_id = engagement_of(user, business_id, item_id)
    business = onboarding.get_business(business_id)
    filing = compliance.get_filings_by_ids([item_id])[item_id]
    if filing.status in compliance.DONE_STATUSES:
        raise ApiError(409, "FILING_LOCKED", "This filing is already filed.")
    if checklist_key != documents.GENERAL_KEY and checklist_key not in (
        compliance.checklist_keys(filing.form_code)
    ):
        raise ApiError(422, "UNKNOWN_CHECKLIST_KEY", "This checklist entry does not exist.")

    message = message.strip()
    document_request = DocumentRequest(
        engagement_id=engagement_id,
        compliance_item_id=item_id,
        checklist_key=checklist_key,
        message=message,
    )
    db.session.add(document_request)
    owner = db.session.get(User, business.user_id)
    title = f"Your CA asked for a document for {compliance.filing_name(filing)}"
    body = f"{user.full_name}: {message}"
    alerts.notify(
        owner, NotificationType.DOCUMENT_REQUEST, title, body, f"/business/compliance/{filing.id}"
    )
    db.session.commit()
    alerts.email_notice(owner, title, body)
    log.info("Document request %s created for filing %s", document_request.id, filing.id)
    return jsonify(request_to_dict(document_request, filing)), 201


@bp.post("/ca-workspace/clients/<uuid:business_id>/filings/<uuid:item_id>/mark-filed")
@roles_required(UserRole.CA)
def mark_filed(business_id, item_id):
    """The CA filed one engaged filing, with an optional ARN and acknowledgement file. The
    business is told; the engagement completes when this was its last filing."""
    acknowledgement_no = compliance.read_acknowledgement_no()
    require_ca_access(business_id)
    user = current_user()
    engagement_id = engagement_of(user, business_id, item_id)
    business = onboarding.get_business(business_id)
    upload = request.files.get("file")
    filing = compliance.mark_filed_by_ca(business, user, item_id, acknowledgement_no, upload)
    # Requests for a filed filing can no longer be answered.
    for document_request in open_requests({engagement_id}, [item_id]):
        document_request.status = DocumentRequestStatus.CANCELLED
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
    return jsonify(
        {
            "compliance_item_id": str(filing.id),
            "status": filing.status,
            "acknowledgement_no": filing.acknowledgement_no,
            "engagement_completed": completed,
        }
    )


@bp.get("/ca-workspace/batches")
@roles_required(UserRole.CA)
def list_batches():
    """The CA's engaged, not-filed filings across clients, grouped by form and due date,
    soonest first, with each client's document readiness."""
    groups = {}
    for business_id, work in work_by_client(ca_profile_id_of(current_user())).items():
        business = onboarding.get_business(business_id)
        for filing in compliance.get_filings_by_ids(list(work)).values():
            if filing.status in compliance.DONE_STATUSES:
                continue
            progress = compliance.checklist_progress(filing)
            groups.setdefault((filing.due_date, filing.form_code), []).append(
                {
                    "business_id": str(business_id),
                    "business_name": business.legal_name,
                    "compliance_item_id": str(filing.id),
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
                "due_date": iso(due_date),
                "ready_count": sum(1 for row in filings if row["ready"]),
                "filings": filings,
            }
        )
    return jsonify(batches)


@bp.post("/ca-workspace/document-requests/<uuid:request_id>/cancel")
@roles_required(UserRole.CA)
def cancel_document_request(request_id):
    """The CA takes an open request back (only for their active work)."""
    document_request = db.session.get(DocumentRequest, request_id)
    engagements = {row[0] for row in marketplace.active_work(ca_profile_id_of(current_user()))}
    if document_request is None or document_request.engagement_id not in engagements:
        raise ApiError(404, "REQUEST_NOT_FOUND", "This document request was not found.")
    if document_request.status != DocumentRequestStatus.OPEN:
        raise ApiError(409, "REQUEST_NOT_OPEN", "This request is no longer open.")
    document_request.status = DocumentRequestStatus.CANCELLED
    db.session.commit()
    return jsonify(request_to_dict(document_request))


# --- Routes for the business -------------------------------------------------------------


@bp.get("/ca-workspace/document-requests")
@roles_required(UserRole.BUSINESS)
def list_business_requests():
    """The business's open document requests from its CAs (its to-dos), oldest first,
    optionally for one filing (?compliance_item_id=). Each has the CA's name."""
    item_id = request.args.get("compliance_item_id")
    if item_id is not None:
        item_id = read_uuid(item_id)
        if item_id is None:
            raise validation_error({"compliance_item_id": ["Not a valid UUID."]}, "query")
    cas = marketplace.active_cas_of_business(current_business().id)
    rows = []
    for document_request in open_requests(set(cas), [item_id] if item_id else None):
        row = request_to_dict(document_request)
        row["ca_name"] = cas[document_request.engagement_id].full_name
        rows.append(row)
    return jsonify(rows)


@bp.post("/ca-workspace/document-requests/<uuid:request_id>/fulfil")
@roles_required(UserRole.BUSINESS)
def fulfil_document_request(request_id):
    """The business answers a request with one of its documents: the file is linked to the
    filing under the requested checklist key (which ticks it), and the CA is told."""
    document_id = json_body().get("document_id")
    if document_id is None:
        raise validation_error({"document_id": [MISSING]})
    if read_uuid(document_id) is None:
        raise validation_error({"document_id": ["Not a valid UUID."]})
    document_id = read_uuid(document_id)
    business = current_business()
    document_request = db.session.get(DocumentRequest, request_id)
    cas = marketplace.active_cas_of_business(business.id)
    if document_request is None or document_request.engagement_id not in cas:
        raise ApiError(404, "REQUEST_NOT_FOUND", "This document request was not found.")
    if document_request.status != DocumentRequestStatus.OPEN:
        raise ApiError(409, "REQUEST_NOT_OPEN", "This request is no longer open.")
    documents.attach_document(
        business,
        current_user(),
        document_id,
        document_request.compliance_item_id,
        document_request.checklist_key,
    )
    document_request.status = DocumentRequestStatus.FULFILLED
    document_request.fulfilled_at = utcnow()
    document_request.document_id = document_id
    filing = compliance.get_filings_by_ids([document_request.compliance_item_id])[
        document_request.compliance_item_id
    ]
    ca_user = cas[document_request.engagement_id]
    title = f"{business.legal_name} sent the document you asked for"
    body = f"For {compliance.filing_name(filing)}: {document_request.message}"
    alerts.notify(
        ca_user, NotificationType.DOCUMENT_REQUEST, title, body, f"/ca/clients/{business.id}"
    )
    db.session.commit()
    alerts.email_notice(ca_user, title, body)
    log.info("Document request %s fulfilled", document_request.id)
    return jsonify(request_to_dict(document_request, filing))
