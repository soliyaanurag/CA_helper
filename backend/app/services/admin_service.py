"""Business logic for admin screens: users, CA verification and the counts on the home page.

get_dashboard(user) -> dict                  the welcome text
get_stats() -> dict                          counts: users, businesses, CAs, open engagements
list_users(role, search, page, page_size)    every account, searchable
list_cas(status) -> list                     CA profiles, e.g. those waiting for verification
get_ca(profile_id) -> dict                   one CA with everything to check
get_ca_certificate(profile_id)               (Document, bytes) of the Certificate of Practice
verify_ca(admin, profile_id) -> dict         verified: listed in the marketplace; the CA is emailed
reject_ca(admin, profile_id, reason) -> dict rejected with a reason; the CA is emailed

The data belongs to other modules, so this file calls their service functions.
"""

import logging

from app.extensions import db
from app.models import User
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


def verify_ca(admin: User, profile_id) -> dict:
    """Verify a CA (their certificate must be uploaded: 409 CERTIFICATE_MISSING)."""
    profile = marketplace_service.set_verification(profile_id, admin, verified=True, reason=None)
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
