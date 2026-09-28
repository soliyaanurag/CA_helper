"""Business logic for admin screens: users, CA verification and the counts on the home page.

get_dashboard(user) -> dict                  the welcome text
get_stats() -> dict                          counts: users, businesses, CAs, open engagements
list_users(role, search, page, page_size)    every account, searchable
list_cas(status) -> list                     CA profiles, e.g. those waiting for verification
get_ca(profile_id) -> dict                   one CA with everything to check
get_ca_certificate(profile_id)               (Document, bytes) of the Certificate of Practice
verify_ca(admin, profile_id) -> dict         verified: listed in the marketplace; the CA is emailed
reject_ca(admin, profile_id, reason) -> dict rejected with a reason; the CA is emailed
suspend_user(admin, user_id, reason) -> User  the account cannot log in (AD4)
reactivate_user(admin, user_id) -> User      it can log in again
list_audit_log(page, page_size) -> dict      every admin action, newest first (AD8)

Every admin action is written to `admin_audit_log` (never PII or document contents).
The data belongs to other modules, so this file calls their service functions.
"""

import logging

from sqlalchemy import select

from app.errors import ApiError
from app.extensions import db
from app.models import AdminAuditLog, User
from app.models.enums import UserRole
from app.services import (
    auth_service,
    compliance_service,
    documents_service,
    marketplace_service,
    onboarding_service,
)
from app.utils.email import send_email

log = logging.getLogger(__name__)


def get_dashboard(user: User) -> dict:
    """Data for the admin home page: a welcome message (the counts come from get_stats)."""
    return {"message": f"Welcome, {user.full_name}"}


def get_stats() -> dict:
    return {
        "users_by_role": auth_service.count_users_by_role(),
        "businesses": onboarding_service.count_businesses(),
        "cas_by_status": marketplace_service.count_cas_by_status(),
        "open_engagements": marketplace_service.count_open_engagements(),
        **compliance_service.filing_stats(),
    }


def list_users(role, search, page: int, page_size: int) -> dict:
    return auth_service.list_users(role, search, page, page_size)


def list_cas(status) -> list[dict]:
    return marketplace_service.list_cas_for_admin(status)


def get_ca(profile_id) -> dict:
    return marketplace_service.get_ca_for_admin(profile_id)


def get_ca_certificate(profile_id):
    return documents_service.read_document(marketplace_service.certificate_document_id(profile_id))


def _audit(admin: User, action: str, target_type: str, target_id, details=None) -> None:
    """Record an admin action. Does not commit."""
    db.session.add(
        AdminAuditLog(
            admin_id=admin.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
    )


def verify_ca(admin: User, profile_id) -> dict:
    """Verify a CA (their certificate must be uploaded: 409 CERTIFICATE_MISSING)."""
    profile = marketplace_service.set_verification(profile_id, admin, verified=True, reason=None)
    _audit(admin, "ca_profile.verify", "ca_profile", profile.id)
    db.session.commit()
    send_email(
        profile.user.email,
        "Your CA Helper profile is verified",
        "ca_verified",
        name=profile.user.full_name,
    )
    log.info("Admin %s verified CA profile %s", admin.id, profile.id)
    return marketplace_service.get_ca_for_admin(profile.id)


def reject_ca(admin: User, profile_id, reason: str) -> dict:
    """Reject a CA with a reason the CA sees (on their profile page and in an email)."""
    profile = marketplace_service.set_verification(profile_id, admin, verified=False, reason=reason)
    _audit(admin, "ca_profile.reject", "ca_profile", profile.id, {"reason": reason})
    db.session.commit()
    send_email(
        profile.user.email,
        "Your CA Helper profile needs a correction",
        "ca_rejected",
        name=profile.user.full_name,
        reason=reason,
    )
    log.info("Admin %s rejected CA profile %s", admin.id, profile.id)
    return marketplace_service.get_ca_for_admin(profile.id)


# --- Suspend and reactivate accounts (AD4) ----------------------------------------------


def suspend_user(admin: User, user_id, reason: str | None) -> User:
    """Suspend an account: it can no longer log in, and a token it still holds stops working.

    A suspended CA leaves the marketplace (only live accounts are listed); their
    unanswered requests and open quotes are cancelled and each business is told. Active
    engagements stay. 409 CANNOT_SUSPEND_SELF, 409 ALREADY_SUSPENDED, 404 USER_NOT_FOUND.
    """
    user = auth_service.get_user_for_admin(user_id)
    if user.id == admin.id:
        raise ApiError(409, "CANNOT_SUSPEND_SELF", "You cannot suspend your own account.")
    if not user.is_active:
        raise ApiError(409, "ALREADY_SUSPENDED", "This account is already suspended.")
    auth_service.set_user_active(user, False)
    cancelled = 0
    if user.role == UserRole.CA:
        cancelled = marketplace_service.cancel_open_requests_of_ca(user)
    _audit(
        admin,
        "user.suspend",
        "user",
        user.id,
        {"reason": reason, "cancelled_requests": cancelled},
    )
    db.session.commit()
    log.info("Admin %s suspended user %s (%d requests cancelled)", admin.id, user.id, cancelled)
    return user


def reactivate_user(admin: User, user_id) -> User:
    """Let a suspended account log in again (cancelled requests stay cancelled).
    409 NOT_SUSPENDED, 404 USER_NOT_FOUND."""
    user = auth_service.get_user_for_admin(user_id)
    if user.is_active:
        raise ApiError(409, "NOT_SUSPENDED", "This account is not suspended.")
    auth_service.set_user_active(user, True)
    _audit(admin, "user.reactivate", "user", user.id)
    db.session.commit()
    log.info("Admin %s reactivated user %s", admin.id, user.id)
    return user


# --- Audit log (AD8) ---------------------------------------------------------------------


def list_audit_log(page: int, page_size: int) -> dict:
    """Every admin action, newest first, paginated. Each row names the admin and, for a
    user or CA profile, the target."""
    stmt = select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id)
    result = db.paginate(stmt, page=page, per_page=page_size, error_out=False)
    rows = result.items
    user_ids = {row.admin_id for row in rows}
    user_ids |= {row.target_id for row in rows if row.target_type == "user"}
    names = auth_service.names_of(user_ids)
    ca_names = marketplace_service.ca_names(
        {row.target_id for row in rows if row.target_type == "ca_profile"}
    )
    items = []
    for row in rows:
        target_name = None
        if row.target_type == "user":
            target_name = names.get(row.target_id)
        if row.target_type == "ca_profile":
            target_name = ca_names.get(row.target_id)
        items.append(
            {
                "id": row.id,
                "admin_name": names.get(row.admin_id),
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "target_name": target_name,
                "details": row.details,
                "created_at": row.created_at,
            }
        )
    return {"items": items, "page": page, "page_size": page_size, "total": result.total}
