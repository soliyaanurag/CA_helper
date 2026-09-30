"""Request and response shapes for /api/v1/compliance/..."""

from marshmallow import Schema, fields, post_load, validate

from app.models.compliance import ComplianceStatus, FilingPath
from app.models.enums import FormCode


class ComplianceItemSchema(Schema):
    """One filing, e.g. GSTR-3B for Apr 2026, due 2026-05-20."""

    id = fields.UUID(required=True)
    form_code = fields.String(validate=validate.OneOf(list(FormCode)), required=True)
    fy = fields.String(required=True, metadata={"description": 'Financial year, e.g. "2026-27"'})
    period_label = fields.String(
        required=True, metadata={"description": '"Apr 2026", "Q1 2026-27"'}
    )
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    due_date = fields.Date(required=True)
    status = fields.String(validate=validate.OneOf(list(ComplianceStatus)), required=True)
    filing_path = fields.String(validate=validate.OneOf(list(FilingPath)), allow_none=True)


class ItemListArgsSchema(Schema):
    """GET /compliance/items filters (CO4); all optional."""

    status = fields.String(validate=validate.OneOf(list(ComplianceStatus)))
    form_code = fields.String(validate=validate.OneOf(list(FormCode)))
    due_from = fields.Date(metadata={"description": "Due on or after this date"})
    due_to = fields.Date(metadata={"description": "Due on or before this date"})


class ComplianceDashboardSchema(Schema):
    """The business home page (CO12)."""

    message = fields.String(required=True, metadata={"description": "Welcome text"})
    registered = fields.Boolean(required=True, metadata={"description": "Business registered?"})
    next_deadline = fields.Nested(ComplianceItemSchema, allow_none=True, required=True)
    due_this_month = fields.Integer(
        required=True, metadata={"description": "Not filed, due later this month"}
    )
    overdue = fields.Integer(required=True, metadata={"description": "Not filed, due date passed"})
    with_ca = fields.Integer(required=True, metadata={"description": "A CA is working on them"})


class ChecklistEntrySchema(Schema):
    """One document to have ready, from content/forms/<FORM>/checklist.yaml."""

    key = fields.String(required=True)
    label = fields.String(required=True)
    required = fields.Boolean(required=True)
    help = fields.String(allow_none=True)


class FormContentSchema(Schema):
    """GET /compliance/forms/<form_code> (CO6). The texts are Markdown."""

    form_code = fields.String(validate=validate.OneOf(list(FormCode)), required=True)
    status = fields.String(required=True, metadata={"description": "TODO, DRAFT or DONE"})
    explanation = fields.String(required=True)
    instructions = fields.String(required=True)
    checklist = fields.List(fields.Nested(ChecklistEntrySchema), required=True)


class TickedChecklistEntrySchema(ChecklistEntrySchema):
    ticked = fields.Boolean(required=True)


class FilingDetailItemSchema(ComplianceItemSchema):
    filed_at = fields.DateTime(allow_none=True)
    acknowledgement_no = fields.String(allow_none=True)


class VerificationSchema(Schema):
    """What the acknowledgement file shows, read locally with OCR (DO8)."""

    verified = fields.Boolean(required=True)
    problems = fields.List(
        fields.String(), required=True, metadata={"description": "What did not match"}
    )
    acknowledgement_no = fields.String(
        allow_none=True, metadata={"description": "The number found"}
    )
    filing_date = fields.String(
        allow_none=True, metadata={"description": "The date found, YYYY-MM-DD"}
    )


class AcknowledgementSchema(Schema):
    filename = fields.String(required=True)
    uploaded_at = fields.DateTime(required=True)
    verification = fields.Nested(VerificationSchema, required=True)


class FilingDetailSchema(Schema):
    """GET /compliance/items/<id> (CO5): the filing page."""

    filing = fields.Nested(FilingDetailItemSchema, required=True)
    form_name = fields.String(required=True, metadata={"description": 'e.g. "GSTR-3B (monthly)"'})
    content_status = fields.String(required=True, metadata={"description": "TODO, DRAFT or DONE"})
    explanation = fields.String(required=True, metadata={"description": "Markdown"})
    instructions = fields.String(required=True, metadata={"description": "Markdown"})
    checklist = fields.List(fields.Nested(TickedChecklistEntrySchema), required=True)
    acknowledgement = fields.Nested(AcknowledgementSchema, allow_none=True, required=True)


class ChoosePathSchema(Schema):
    """POST /compliance/items/<id>/path (CO8)."""

    path = fields.String(validate=validate.OneOf(list(FilingPath)), required=True)


class ChecklistTickSchema(Schema):
    """POST /compliance/items/<id>/checklist (CO7)."""

    key = fields.String(required=True, validate=validate.Length(1, 50))
    ticked = fields.Boolean(required=True)


class MarkFiledFormSchema(Schema):
    """POST /compliance/items/<id>/mark-filed (multipart/form-data), the text part."""

    acknowledgement_no = fields.String(load_default=None, validate=validate.Length(max=50))

    @post_load
    def _clean(self, data: dict, **kwargs) -> dict:
        if data["acknowledgement_no"] is not None:
            data["acknowledgement_no"] = data["acknowledgement_no"].strip().upper() or None
        return data


class MarkFiledFileSchema(Schema):
    """The optional acknowledgement file (PDF, JPG or PNG)."""

    file = fields.Raw(load_default=None, metadata={"type": "string", "format": "binary"})


class PeerPathSchema(Schema):
    count = fields.Integer(required=True, metadata={"description": "Filed filings on this path"})
    share_pct = fields.Integer(allow_none=True, metadata={"description": "Of all filed, %"})
    on_time_pct = fields.Integer(allow_none=True, metadata={"description": "Filed on time, %"})


class PeerInsightsSchema(Schema):
    """GET /compliance/items/<id>/peer-insights (CO13)."""

    form_code = fields.String(validate=validate.OneOf(list(FormCode)), required=True)
    scope = fields.String(
        required=True,
        metadata={"description": '"segment" (same entity type and MSME tier), "overall" or "none"'},
    )
    entity_type = fields.String(required=True)
    msme_tier = fields.String(allow_none=True)
    min_businesses = fields.Integer(required=True)
    business_count = fields.Integer(required=True)
    filing_count = fields.Integer(required=True)
    self = fields.Nested(PeerPathSchema, allow_none=True, required=True)
    ca = fields.Nested(PeerPathSchema, allow_none=True, required=True)
