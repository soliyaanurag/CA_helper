"""HTTP routes for admin: /api/v1/admin/... (admins only)

    GET  /admin/dashboard                  the welcome text
    GET  /admin/stats                      counts for the home page
    GET  /admin/users?role=&search=&page=  every account
    GET  /admin/cas?status=pending         CA profiles (pending ones wait for verification)
    GET  /admin/cas/<id>                   one CA with everything to check
    GET  /admin/cas/<id>/certificate       the Certificate of Practice file (admins only)
    POST /admin/cas/<id>/verify            verify the CA
    POST /admin/cas/<id>/reject            reject with a reason
    POST /admin/users/<id>/suspend         suspend an account (AD4)
    POST /admin/users/<id>/reactivate      let it log in again
    GET  /admin/audit-log?page=            every admin action, newest first (AD8)

Routes stay thin: parse input (app/schemas/), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

import io

from flask import send_file
from flask.views import MethodView
from flask_smorest import Blueprint

from app.errors import ErrorSchema
from app.models.enums import UserRole
from app.schemas.admin import (
    AdminCaArgsSchema,
    AdminCaSchema,
    AdminDashboardSchema,
    AdminStatsSchema,
    AdminUserArgsSchema,
    AdminUserPageSchema,
    AdminUserSchema,
    AuditLogArgsSchema,
    AuditLogPageSchema,
    RejectCaInputSchema,
    SuspendUserInputSchema,
)
from app.services import admin_service
from app.utils.decorators import current_user, roles_required

blp = Blueprint("admin", __name__, description="Admin: users, CA verification and service catalog")


@blp.route("/admin/dashboard")
class AdminDashboard(MethodView):
    @roles_required(UserRole.ADMIN)
    @blp.response(200, AdminDashboardSchema)
    def get(self):
        return admin_service.get_dashboard(current_user())


@blp.route("/admin/stats", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.response(200, AdminStatsSchema)
def get_stats():
    return admin_service.get_stats()


@blp.route("/admin/users", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.arguments(AdminUserArgsSchema, location="query")
@blp.response(200, AdminUserPageSchema)
def list_users(args):
    return admin_service.list_users(
        args.get("role"), args.get("search"), args["page"], args["page_size"]
    )


@blp.route("/admin/cas", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.arguments(AdminCaArgsSchema, location="query")
@blp.response(200, AdminCaSchema(many=True))
def list_cas(args):
    return admin_service.list_cas(args.get("status"))


@blp.route("/admin/cas/<uuid:ca_id>", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.response(200, AdminCaSchema)
@blp.alt_response(404, schema=ErrorSchema, description="CA_NOT_FOUND")
def get_ca(ca_id):
    return admin_service.get_ca(ca_id)


@blp.route("/admin/cas/<uuid:ca_id>/certificate", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.response(200, description="The certificate file (PDF, JPG or PNG)")
@blp.alt_response(404, schema=ErrorSchema, description="CA_NOT_FOUND, CERTIFICATE_MISSING")
def get_ca_certificate(ca_id):
    document, data = admin_service.get_ca_certificate(ca_id)
    return send_file(
        io.BytesIO(data), mimetype=document.mime_type, download_name=document.original_filename
    )


@blp.route("/admin/cas/<uuid:ca_id>/verify", methods=["POST"])
@roles_required(UserRole.ADMIN)
@blp.response(200, AdminCaSchema)
@blp.alt_response(409, schema=ErrorSchema, description="CERTIFICATE_MISSING")
def verify_ca(ca_id):
    return admin_service.verify_ca(current_user(), ca_id)


@blp.route("/admin/cas/<uuid:ca_id>/reject", methods=["POST"])
@roles_required(UserRole.ADMIN)
@blp.arguments(RejectCaInputSchema)
@blp.response(200, AdminCaSchema)
def reject_ca(data, ca_id):
    return admin_service.reject_ca(current_user(), ca_id, data["reason"].strip())


@blp.route("/admin/users/<uuid:user_id>/suspend", methods=["POST"])
@roles_required(UserRole.ADMIN)
@blp.arguments(SuspendUserInputSchema)
@blp.response(200, AdminUserSchema)
@blp.alt_response(404, schema=ErrorSchema, description="USER_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="CANNOT_SUSPEND_SELF, ALREADY_SUSPENDED")
def suspend_user(data, user_id):
    reason = data["reason"].strip() if data["reason"] else None
    return admin_service.suspend_user(current_user(), user_id, reason or None)


@blp.route("/admin/users/<uuid:user_id>/reactivate", methods=["POST"])
@roles_required(UserRole.ADMIN)
@blp.response(200, AdminUserSchema)
@blp.alt_response(404, schema=ErrorSchema, description="USER_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="NOT_SUSPENDED")
def reactivate_user(user_id):
    return admin_service.reactivate_user(current_user(), user_id)


@blp.route("/admin/audit-log", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.arguments(AuditLogArgsSchema, location="query")
@blp.response(200, AuditLogPageSchema)
def list_audit_log(args):
    return admin_service.list_audit_log(args["page"], args["page_size"])
