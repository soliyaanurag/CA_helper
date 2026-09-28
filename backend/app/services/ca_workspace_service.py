"""Business logic for the CA's multi-client dashboard and client workspace.

get_dashboard(user) -> dict                               welcome text for the CA home page
list_clients(user, today) -> list                         clients by urgency (CW2, CW6)
get_client(user, business_id) -> dict                     one client's workspace (CW3)
list_batches(user, today) -> list                         engaged filings by form + due date (CW7)
create_document_request(user, business_id, ...) -> dict   ask the client for a document (CW4)
cancel_document_request(user, request_id) -> dict         the CA takes the request back
list_business_requests(business, item_id) -> list         the business's open requests (its to-dos)
fulfil_document_request(business, user, id, doc_id)       the business answers with a file
mark_filed_for_client(user, business_id, item_id, ...)    the CA filed one filing (CW5)

A CA works only on the filings of their ACTIVE engagements (marketplace_service,
CLAUDE.md rule 5). Every route that names a business calls require_ca_access() first;
the service then keeps to active_work(), so a CA with two clients, or a business with
two CAs, never mixes them up.

Urgency (CW6): a simple weighted sum, each part with its reason, so the CA sees why a
client is flagged. The weights are the constants below; regulatory changes add points
through regulatory_points() (approved changes from the regulatory module).
"""

import logging
from datetime import date

from sqlalchemy import select

from app.errors import ApiError
from app.extensions import db
from app.models import DocumentRequest, User
from app.models.alerts import NotificationType
from app.models.base import today_in_india, utcnow
from app.models.ca_workspace import DocumentRequestStatus
from app.services import (
    alerts_service,
    compliance_service,
    documents_service,
    marketplace_service,
    onboarding_service,
    regulatory_service,
)

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
    ca_profile_id = marketplace_service.own_profile_id(user)
    if ca_profile_id is None:
        raise ApiError(404, "CA_PROFILE_NOT_FOUND", "Save your CA profile first.")
    return ca_profile_id


def _work_by_client(ca_profile_id) -> dict:
    """{business id: {filing id: engagement id}} for the CA's ACTIVE engagements."""
    clients = {}
    for engagement_id, business_id, item_id in marketplace_service.active_work(ca_profile_id):
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
    for change in regulatory_service.active_changes_for(business_id):
        forms = regulatory_service.forms_text(change.form_codes)
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
        missing += len(compliance_service.checklist_progress(filing)["missing"])

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
        business = onboarding_service.get_business(business_id)
        filings = compliance_service.get_filings_by_ids(list(work)).values()
        not_filed = [f for f in filings if f.status not in compliance_service.DONE_STATUSES]
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
    filing = filing or compliance_service.get_filings_by_ids([request.compliance_item_id]).get(
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
    business = onboarding_service.get_business(business_id)
    filings = sorted(
        compliance_service.get_filings_by_ids(list(work)).values(), key=lambda f: f.due_date
    )
    documents = documents_service.documents_by_filing(filings)
    requests = {}
    for request in _open_requests(set(work.values()), list(work)):
        requests.setdefault(request.compliance_item_id, []).append(request)

    rows = []
    for filing in filings:
        rows.append(
            {
                "filing": filing,
                "checklist": compliance_service.checklist_with_ticks(filing),
                "documents": documents[filing.id],
                "open_requests": [
                    _request_details(request, filing) for request in requests.get(filing.id, [])
                ],
            }
        )
    return {**onboarding_service.get_my_business(business), "filings": rows}


def list_batches(user: User, today: date | None = None) -> list[dict]:
    """The CA's engaged, not-filed filings across clients, grouped by form and due date,
    soonest first, with each client's document readiness (CW7)."""
    groups = {}
    for business_id, work in _work_by_client(_ca_profile_id(user)).items():
        business = onboarding_service.get_business(business_id)
        for filing in compliance_service.get_filings_by_ids(list(work)).values():
            if filing.status in compliance_service.DONE_STATUSES:
                continue
            progress = compliance_service.checklist_progress(filing)
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
    business = onboarding_service.get_business(business_id)
    filing = compliance_service.get_filings_by_ids([item_id])[item_id]
    if filing.status in compliance_service.DONE_STATUSES:
        raise ApiError(409, "FILING_LOCKED", "This filing is already filed.")
    if checklist_key != documents_service.GENERAL_KEY and checklist_key not in (
        compliance_service.checklist_keys(filing.form_code)
    ):
        raise ApiError(422, "UNKNOWN_CHECKLIST_KEY", "This checklist entry does not exist.")

    request = DocumentRequest(
        engagement_id=engagement_id,
        compliance_item_id=item_id,
        checklist_key=checklist_key,
        message=message,
    )
    db.session.add(request)
    form = compliance_service.FORM_FOLDERS[filing.form_code]
    alerts_service.notify(
        db.session.get(User, business.user_id),
        NotificationType.DOCUMENT_REQUEST,
        f"Your CA asked for a document for {form} ({filing.period_label})",
        f"{user.full_name}: {message}",
        f"/business/compliance/{filing.id}",
        email=True,
    )
    db.session.commit()
    log.info("Document request %s created for filing %s", request.id, filing.id)
    return _request_details(request, filing)


def cancel_document_request(user: User, request_id) -> dict:
    """The CA takes an open request back. 404 REQUEST_NOT_FOUND (not theirs, or not active
    work any more); 409 REQUEST_NOT_OPEN."""
    request = db.session.get(DocumentRequest, request_id)
    engagements = {row[0] for row in marketplace_service.active_work(_ca_profile_id(user))}
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
    cas = marketplace_service.active_cas_of_business(business.id)
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
    cas = marketplace_service.active_cas_of_business(business.id)
    if request is None or request.engagement_id not in cas:
        raise ApiError(404, "REQUEST_NOT_FOUND", "This document request was not found.")
    if request.status != DocumentRequestStatus.OPEN:
        raise ApiError(409, "REQUEST_NOT_OPEN", "This request is no longer open.")
    documents_service.attach_document(
        business, user, document_id, request.compliance_item_id, request.checklist_key
    )
    request.status = DocumentRequestStatus.FULFILLED
    request.fulfilled_at = utcnow()
    request.document_id = document_id
    filing = compliance_service.get_filings_by_ids([request.compliance_item_id])[
        request.compliance_item_id
    ]
    alerts_service.notify(
        cas[request.engagement_id],
        NotificationType.DOCUMENT_REQUEST,
        f"{business.legal_name} sent the document you asked for",
        f"For {compliance_service.FORM_FOLDERS[filing.form_code]} ({filing.period_label}): "
        f"{request.message}",
        f"/ca/clients/{business.id}",
        email=True,
    )
    db.session.commit()
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
    business = onboarding_service.get_business(business_id)
    filing = compliance_service.mark_filed_by_ca(
        business, user, item_id, acknowledgement_no, upload
    )
    # Requests for a filed filing can no longer be answered.
    for request in _open_requests({engagement_id}, [item_id]):
        request.status = DocumentRequestStatus.CANCELLED
    alerts_service.notify(
        db.session.get(User, business.user_id),
        NotificationType.ENGAGEMENT_UPDATE,
        f"Your CA filed {compliance_service.FORM_FOLDERS[filing.form_code]} "
        f"({filing.period_label})",
        f"{user.full_name} marked it as filed"
        + (
            f" (acknowledgement number {filing.acknowledgement_no})."
            if filing.acknowledgement_no
            else "."
        ),
        f"/business/compliance/{filing.id}",
        email=True,
    )
    completed = marketplace_service.complete_if_all_filed(engagement_id)
    db.session.commit()
    return {
        "compliance_item_id": filing.id,
        "status": filing.status,
        "acknowledgement_no": filing.acknowledgement_no,
        "engagement_completed": completed,
    }
