"""Routes for the regulatory monitor (all under /api/v1, admins only).

    GET  /admin/regulatory/changes?status=      changes found in the news, newest first
    POST /admin/regulatory/changes/<id>/approve  approve: affected businesses are told
    POST /admin/regulatory/changes/<id>/reject   reject: nobody is told
    GET  /admin/regulatory/sources               the news sources
    POST /admin/regulatory/sources               add a source
    PUT  /admin/regulatory/sources/<id>          switch a source on or off
    POST /admin/regulatory/scan                  run the news scan now (demo)

The scan also runs on demand: `flask regulatory scan` (RE6), and every morning in the
worker (backend/worker.py).
"""

import click
from flask_smorest import Blueprint

from app.errors import ErrorSchema
from app.extensions import limiter
from app.models.enums import UserRole
from app.schemas.regulatory import (
    ChangeListArgsSchema,
    NewsSourceEnabledSchema,
    NewsSourceInputSchema,
    NewsSourceSchema,
    RegulatoryChangeSchema,
    ScanResultSchema,
)
from app.services import regulatory_service
from app.utils.decorators import current_user, roles_required

blp = Blueprint("regulatory", __name__, description="Regulatory news monitor (admin)")


# The changes found in the news (pending ones wait for an admin).
@blp.route("/admin/regulatory/changes", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.arguments(ChangeListArgsSchema, location="query")
@blp.response(200, RegulatoryChangeSchema(many=True))
def list_changes(args):
    status = None
    if args["status"] is not None:
        status = args["status"].value
    return regulatory_service.list_changes(status)


# Approve a change: the affected businesses get a tray entry and an email, their CAs a
# tray entry, and the client's urgency rises.
@blp.route("/admin/regulatory/changes/<uuid:change_id>/approve", methods=["POST"])
@roles_required(UserRole.ADMIN)
@blp.response(200, RegulatoryChangeSchema)
@blp.alt_response(404, schema=ErrorSchema, description="CHANGE_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="CHANGE_NOT_PENDING (already reviewed)")
def approve_change(change_id):
    return regulatory_service.approve_change(current_user(), change_id)


# Reject a change: nobody is told.
@blp.route("/admin/regulatory/changes/<uuid:change_id>/reject", methods=["POST"])
@roles_required(UserRole.ADMIN)
@blp.response(200, RegulatoryChangeSchema)
@blp.alt_response(404, schema=ErrorSchema, description="CHANGE_NOT_FOUND")
@blp.alt_response(409, schema=ErrorSchema, description="CHANGE_NOT_PENDING (already reviewed)")
def reject_change(change_id):
    return regulatory_service.reject_change(current_user(), change_id)


@blp.route("/admin/regulatory/sources", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.response(200, NewsSourceSchema(many=True))
def list_sources():
    return regulatory_service.list_sources()


@blp.route("/admin/regulatory/sources", methods=["POST"])
@roles_required(UserRole.ADMIN)
@blp.arguments(NewsSourceInputSchema)
@blp.response(201, NewsSourceSchema)
@blp.alt_response(409, schema=ErrorSchema, description="SOURCE_EXISTS")
def add_source(data):
    return regulatory_service.add_source(data)


@blp.route("/admin/regulatory/sources/<uuid:source_id>", methods=["PUT"])
@roles_required(UserRole.ADMIN)
@blp.arguments(NewsSourceEnabledSchema)
@blp.response(200, NewsSourceSchema)
@blp.alt_response(404, schema=ErrorSchema, description="SOURCE_NOT_FOUND")
def set_source_enabled(data, source_id):
    return regulatory_service.set_source_enabled(source_id, data["enabled"])


# Run the news scan now (for demos). It downloads every enabled source, so it is slow
# and limited per minute.
@blp.route("/admin/regulatory/scan", methods=["POST"])
@limiter.limit("2 per minute")
@roles_required(UserRole.ADMIN)
@blp.response(200, ScanResultSchema)
@blp.alt_response(429, schema=ErrorSchema, description="TOO_MANY_REQUESTS (rate limit per IP)")
def scan_now():
    return regulatory_service.scan_news()


# `flask regulatory scan`: run the news scan now (what the worker does every morning).
@blp.cli.command("scan")
def scan_command():
    """Fetch the news sources, save new articles and the changes found in them."""
    counts = regulatory_service.scan_news()
    click.echo(
        f"Sources: {counts['sources']}, blocked by robots.txt: {counts['blocked_by_robots']}, "
        f"failed: {counts['failed']}, new articles: {counts['new_articles']}, "
        f"new changes to review: {counts['changes']}"
    )
