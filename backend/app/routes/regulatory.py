"""Routes for the regulatory monitor (all under /api/v1).

    GET  /regulatory/updates                     the changes about my forms (business, CA)
    GET  /admin/regulatory/changes               changes found in the news, newest first (admin)
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
from app.models.enums import UserRole
from app.schemas.regulatory import (
    NewsSourceEnabledSchema,
    NewsSourceInputSchema,
    NewsSourceSchema,
    RegulatoryChangeSchema,
    ScanResultSchema,
)
from app.services import regulatory_service
from app.utils.decorators import current_user, roles_required

blp = Blueprint("regulatory", __name__, description="Regulatory news monitor")


# The changes about my forms: a business's own filings, a CA's active clients' filings.
@blp.route("/regulatory/updates", methods=["GET"])
@roles_required(UserRole.BUSINESS, UserRole.CA)
@blp.response(200, RegulatoryChangeSchema(many=True))
def list_updates():
    return regulatory_service.list_updates(current_user())


# Every change found in the news. Those Gemini extracted were sent to the affected users
# at once; those found by keywords only were not sent to anyone.
@blp.route("/admin/regulatory/changes", methods=["GET"])
@roles_required(UserRole.ADMIN)
@blp.response(200, RegulatoryChangeSchema(many=True))
def list_changes():
    return regulatory_service.list_changes()


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
@roles_required(UserRole.ADMIN)
@blp.response(200, ScanResultSchema)
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
        f"new changes: {counts['changes']}"
    )
