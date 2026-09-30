"""Request and response shapes for /api/v1/admin/...

Business logic for admin screens: users, CA verification and the counts on the home page.

get_dashboard(user) -> dict                  the welcome text
get_stats() -> dict                          counts: users, businesses, CAs, open engagements
list_users(role, search, page, page_size)    every account, searchable
list_cas(status) -> list                     CA profiles, e.g. those waiting for verification
get_ca(profile_id) -> dict                   one CA with everything to check
get_ca_certificate(profile_id)               (Document, bytes) of the Certificate of Practice
verify_ca(admin, profile_id) -> dict         verified: listed in the marketplace; the CA is emailed
reject_ca(admin, profile_id, reason) -> dict rejected with a reason; the CA is emailed

The data belongs to other modules, so this file calls their service functions.

HTTP routes for admin: /api/v1/admin/... (admins only)

    GET  /admin/dashboard                  the welcome text
    GET  /admin/stats                      counts for the home page
    GET  /admin/users?role=&search=&page=  every account
    GET  /admin/cas?status=pending         CA profiles (pending ones wait for verification)
    GET  /admin/cas/<id>                   one CA with everything to check
    GET  /admin/cas/<id>/certificate       the Certificate of Practice file (admins only)
    POST /admin/cas/<id>/verify            verify the CA
    POST /admin/cas/<id>/reject            reject with a reason

Routes stay thin: parse input (app/schemas/), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

import io
import logging

from flask import send_file
from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import fields, Schema, validate

from app import auth, compliance, documents, marketplace, onboarding
from app.models import CaVerificationStatus, db, User, UserRole
from app.utils import (
    current_user,
    ErrorSchema,
    PageArgsSchema,
    PageSchema,
    roles_required,
    send_email,
)


# --- Request and response shapes ---------------------------------------------------------


class AdminDashboardSchema(Schema):
    message = fields.String(required=True, metadata={"description": "Welcome text"})


class AdminStatsSchema(Schema):
    users_by_role = fields.Dict(keys=fields.String(), values=fields.Integer(), required=True)
    businesses = fields.Integer(required=True)
    cas_by_status = fields.Dict(keys=fields.String(), values=fields.Integer(), required=True)
    open_engagements = fields.Integer(required=True)
    filings_by_status = fields.Dict(
        keys=fields.String(),
        values=fields.Integer(),
        required=True,
        metadata={"description": "AD5"},
    )
    filings_due_so_far = fields.Integer(required=True, metadata={"description": "Due date passed"})
    filings_late = fields.Integer(
        required=True, metadata={"description": "Of those: not filed, or filed after the due date"}
    )
    overdue_rate = fields.Float(
        allow_none=True, metadata={"description": "filings_late / filings_due_so_far, in percent"}
    )


class AdminUserArgsSchema(PageArgsSchema):
    role = fields.String(validate=validate.OneOf(list(UserRole)))
    search = fields.String(validate=validate.Length(max=100))


class AdminUserSchema(Schema):
    id = fields.UUID(required=True)
    full_name = fields.String(required=True)
    email = fields.String(required=True)
    role = fields.String(validate=validate.OneOf(list(UserRole)), required=True)
    email_verified = fields.Function(lambda user: user.email_verified_at is not None)
    created_at = fields.DateTime(required=True)


class AdminUserPageSchema(PageSchema):
    items = fields.List(fields.Nested(AdminUserSchema), required=True)


class AdminCaArgsSchema(Schema):
    status = fields.String(validate=validate.OneOf(list(CaVerificationStatus)))


class AdminCaSchema(Schema):
    """A CA profile with everything an admin checks (including the CoP number)."""

    id = fields.UUID(required=True)
    user_id = fields.UUID(required=True)
    full_name = fields.String(required=True)
    email = fields.String(required=True)
    membership_no = fields.String(required=True)
    cop_number = fields.String(required=True)
    city = fields.String(required=True)
    languages = fields.List(fields.String(), required=True)
    specializations = fields.List(fields.String(), required=True)
    capacity = fields.Integer(required=True)
    years_experience = fields.Integer(required=True)
    pro_bono_slots_per_month = fields.Integer(required=True)
    about = fields.String(required=True)
    verification_status = fields.String(validate=validate.OneOf(list(CaVerificationStatus)), required=True)
    rejection_reason = fields.String(allow_none=True)
    verified_at = fields.DateTime(allow_none=True)
    has_certificate = fields.Boolean(required=True)
    updated_at = fields.DateTime(required=True)


def _not_blank(value: str) -> None:
    if not value.strip():
        raise validate.ValidationError("Give a reason.")


class RejectCaInputSchema(Schema):
    reason = fields.String(required=True, validate=[validate.Length(1, 500), _not_blank])


# --- Logic -------------------------------------------------------------------------------


log = logging.getLogger(__name__)


def get_dashboard(user: User) -> dict:
    """Data for the admin home page: a welcome message (the counts come from get_stats)."""
    return {"message": f"Welcome, {user.full_name}"}


def get_stats() -> dict:
    return {
        "users_by_role": auth.count_users_by_role(),
        "businesses": onboarding.count_businesses(),
        "cas_by_status": marketplace.count_cas_by_status(),
        "open_engagements": marketplace.count_open_engagements(),
        **compliance.filing_stats(),
    }


def list_users(role, search, page: int, page_size: int) -> dict:
    return auth.list_users(role, search, page, page_size)


def list_cas(status) -> list[dict]:
    return marketplace.list_cas_for_admin(status)


def get_ca(profile_id) -> dict:
    return marketplace.get_ca_for_admin(profile_id)


def get_ca_certificate(profile_id):
    return documents.read_document(marketplace.certificate_document_id(profile_id))


def verify_ca(admin: User, profile_id) -> dict:
    """Verify a CA (their certificate must be uploaded: 409 CERTIFICATE_MISSING)."""
    profile = marketplace.set_verification(profile_id, admin, verified=True, reason=None)
    db.session.commit()
    if profile.user.email_notifications:
        send_email(
            profile.user.email,
            "Your CA Helper profile is verified",
            "ca_verified",
            name=profile.user.full_name,
        )
    log.info("Admin %s verified CA profile %s", admin.id, profile.id)
    return marketplace.get_ca_for_admin(profile.id)


def reject_ca(admin: User, profile_id, reason: str) -> dict:
    """Reject a CA with a reason the CA sees (on their profile page and in an email)."""
    profile = marketplace.set_verification(profile_id, admin, verified=False, reason=reason)
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
    return marketplace.get_ca_for_admin(profile.id)


# --- Routes ------------------------------------------------------------------------------


blp = Blueprint("admin", __name__, description="Admin: users, CA verification and service catalog")


@blp.route("/admin/dashboard")
class AdminDashboard(MethodView):
    @roles_required(UserRole.ADMIN)
    @blp.response(200, AdminDashboardSchema)
    def get(self):
        return get_dashboard(current_user())


@blp.route("/admin/stats", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.response(200, AdminStatsSchema)
def get_stats_view():
    return get_stats()


@blp.route("/admin/users", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.arguments(AdminUserArgsSchema, location="query")
@blp.response(200, AdminUserPageSchema)
def list_users_view(args):
    return list_users(
        args.get("role"), args.get("search"), args["page"], args["page_size"]
    )


@blp.route("/admin/cas", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.arguments(AdminCaArgsSchema, location="query")
@blp.response(200, AdminCaSchema(many=True))
def list_cas_view(args):
    return list_cas(args.get("status"))


@blp.route("/admin/cas/<uuid:ca_id>", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.response(200, AdminCaSchema)
@blp.alt_response(404, schema=ErrorSchema, description="CA_NOT_FOUND")
def get_ca_view(ca_id):
    return get_ca(ca_id)


@blp.route("/admin/cas/<uuid:ca_id>/certificate", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.response(200, description="The certificate file (PDF, JPG or PNG)")
@blp.alt_response(404, schema=ErrorSchema, description="CA_NOT_FOUND, CERTIFICATE_MISSING")
def get_ca_certificate_view(ca_id):
    document, data = get_ca_certificate(ca_id)
    return send_file(
        io.BytesIO(data), mimetype=document.mime_type, download_name=document.original_filename
    )


@blp.route("/admin/cas/<uuid:ca_id>/verify", methods=["POST"])
@roles_required(UserRole.ADMIN)
@blp.response(200, AdminCaSchema)
@blp.alt_response(409, schema=ErrorSchema, description="CERTIFICATE_MISSING")
def verify_ca_view(ca_id):
    return verify_ca(current_user(), ca_id)


@blp.route("/admin/cas/<uuid:ca_id>/reject", methods=["POST"])
@roles_required(UserRole.ADMIN)
@blp.arguments(RejectCaInputSchema)
@blp.response(200, AdminCaSchema)
def reject_ca_view(data, ca_id):
    return reject_ca(current_user(), ca_id, data["reason"].strip())
