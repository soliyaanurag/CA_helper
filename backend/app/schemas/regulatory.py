"""Request and response shapes for /api/v1/admin/regulatory/..."""

from marshmallow import Schema, fields, validate

from app.models.regulatory import NewsSourceKind, RegulatoryChangeStatus


class ChangeListArgsSchema(Schema):
    """?status=pending | approved | rejected (empty = all)."""

    status = fields.Enum(RegulatoryChangeStatus, by_value=True, load_default=None)


class RegulatoryChangeSchema(Schema):
    """A change extracted from a news article, with the article it came from."""

    id = fields.UUID(required=True)
    change_type = fields.String(required=True)
    summary = fields.String(required=True)
    form_codes = fields.List(fields.String(), required=True)
    # Who it is for: {extracted_by: "ai" | "keywords", gst_schemes?, entity_types?, states?}
    affected_categories = fields.Dict(required=True)
    # {old_due_date?, new_due_date?, period?}
    dates = fields.Dict(required=True)
    status = fields.String(required=True)
    created_at = fields.DateTime(required=True)
    reviewed_at = fields.DateTime(allow_none=True)
    article_title = fields.String(required=True)
    article_url = fields.String(required=True)
    published_at = fields.DateTime(allow_none=True)
    source_name = fields.String(required=True)
    match_count = fields.Integer(required=True)  # businesses told about it (after approval)


class NewsSourceSchema(Schema):
    id = fields.UUID(required=True)
    name = fields.String(required=True)
    url = fields.String(required=True)
    kind = fields.Enum(NewsSourceKind, by_value=True, required=True)
    enabled = fields.Boolean(required=True)


class NewsSourceInputSchema(Schema):
    """POST /admin/regulatory/sources: a new RSS feed or official update page."""

    name = fields.String(required=True, validate=validate.Length(1, 100))
    url = fields.URL(required=True, schemes={"https", "http"}, validate=validate.Length(max=500))
    kind = fields.Enum(NewsSourceKind, by_value=True, required=True)


class NewsSourceEnabledSchema(Schema):
    enabled = fields.Boolean(required=True)


class ScanResultSchema(Schema):
    sources = fields.Integer(required=True)
    blocked_by_robots = fields.Integer(required=True)
    failed = fields.Integer(required=True)
    new_articles = fields.Integer(required=True)
    changes = fields.Integer(required=True)
