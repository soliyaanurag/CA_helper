"""Admin screens: the counts on the home page, every account, and checking CAs (verify or
reject, with the Certificate of Practice). Admins see metadata only, never document
contents other than a CA's certificate."""

import io
import logging

from flask import Blueprint, jsonify, request, send_file

from app import auth, compliance, documents, marketplace, onboarding
from app.models import CaVerificationStatus, UserRole, db
from app.utils import (
    MISSING,
    current_user,
    iso,
    json_body,
    read_page_args,
    roles_required,
    send_email,
    validation_error,
)

log = logging.getLogger(__name__)

bp = Blueprint("admin", __name__)


@bp.get("/admin/dashboard")
@roles_required(UserRole.ADMIN)
def dashboard():
    return jsonify({"message": f"Welcome, {current_user().full_name}"})


@bp.get("/admin/stats")
@roles_required(UserRole.ADMIN)
def get_stats():
    """Counts for the home page: users, businesses, CAs, open engagements and filings."""
    stats = {
        "users_by_role": auth.count_users_by_role(),
        "businesses": onboarding.count_businesses(),
        "cas_by_status": marketplace.count_cas_by_status(),
        "open_engagements": marketplace.count_open_engagements(),
    }
    stats.update(compliance.filing_stats())
    return jsonify(stats)


@bp.get("/admin/users")
@roles_required(UserRole.ADMIN)
def list_users():
    """Every account, newest first, optionally of one role and matching ?search= (name or
    email), paginated."""
    errors = {}
    page, page_size = read_page_args(errors)
    role = request.args.get("role")
    if role is not None and role not in list(UserRole):
        errors["role"] = [f"Must be one of: {', '.join(UserRole)}."]
    search = request.args.get("search")
    if search is not None and len(search) > 100:
        errors["search"] = ["Longer than maximum length 100."]
    if errors:
        raise validation_error(errors, "query")
    result = auth.list_users(role, search, page, page_size)
    result["items"] = [
        {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "email_verified": user.email_verified_at is not None,
            "created_at": iso(user.created_at),
        }
        for user in result["items"]
    ]
    return jsonify(result)


@bp.get("/admin/cas")
@roles_required(UserRole.ADMIN)
def list_cas():
    """CA profiles (?status=pending|verified|rejected), the longest-waiting first."""
    status = request.args.get("status")
    if status is not None and status not in list(CaVerificationStatus):
        raise validation_error(
            {"status": [f"Must be one of: {', '.join(CaVerificationStatus)}."]}, "query"
        )
    return jsonify(marketplace.list_cas_for_admin(status))


@bp.get("/admin/cas/<uuid:ca_id>")
@roles_required(UserRole.ADMIN)
def get_ca(ca_id):
    return jsonify(marketplace.get_ca_for_admin(ca_id))


@bp.get("/admin/cas/<uuid:ca_id>/certificate")
@roles_required(UserRole.ADMIN)
def get_ca_certificate(ca_id):
    """The CA's Certificate of Practice file, to check it."""
    document, data = documents.read_document(marketplace.certificate_document_id(ca_id))
    return send_file(
        io.BytesIO(data), mimetype=document.mime_type, download_name=document.original_filename
    )


@bp.post("/admin/cas/<uuid:ca_id>/verify")
@roles_required(UserRole.ADMIN)
def verify_ca(ca_id):
    """Verify a CA: listed in the marketplace from now on. The certificate must be uploaded
    (409 CERTIFICATE_MISSING). The CA is emailed."""
    admin = current_user()
    profile = marketplace.set_verification(ca_id, admin, verified=True, reason=None)
    db.session.commit()
    if profile.user.email_notifications:
        send_email(
            profile.user.email,
            "Your CA Helper profile is verified",
            "ca_verified",
            name=profile.user.full_name,
        )
    log.info("Admin %s verified CA profile %s", admin.id, profile.id)
    return jsonify(marketplace.get_ca_for_admin(profile.id))


@bp.post("/admin/cas/<uuid:ca_id>/reject")
@roles_required(UserRole.ADMIN)
def reject_ca(ca_id):
    """Reject a CA with a reason the CA sees (on their profile page and in an email)."""
    reason = json_body().get("reason")
    if reason is None:
        raise validation_error({"reason": [MISSING]})
    if not isinstance(reason, str) or not 1 <= len(reason) <= 500:
        raise validation_error({"reason": ["Length must be between 1 and 500."]})
    if not reason.strip():
        raise validation_error({"reason": ["Give a reason."]})
    admin = current_user()
    reason = reason.strip()
    profile = marketplace.set_verification(ca_id, admin, verified=False, reason=reason)
    db.session.commit()
    if profile.user.email_notifications:
        send_email(
            profile.user.email,
            "Your CA Helper profile needs a correction",
            "ca_rejected",
            name=profile.user.full_name,
            reason=reason,
        )
    log.info("Admin %s rejected CA profile %s", admin.id, profile.id)
    return jsonify(marketplace.get_ca_for_admin(profile.id))
