"""Request and response shapes for /api/v1/compliance/..."""

from marshmallow import Schema, fields, post_load, validate

from app.models.compliance import ComplianceStatus, FilingPath
from app.models.enums import FormCode


class ComplianceItemSchema(Schema):
    """One filing, e.g. GSTR-3B for Apr 2026, due 2026-05-20."""

    id = fields.UUID(required=True)
    form_code = fields.Enum(FormCode, by_value=True, required=True)
    fy = fields.String(required=True, metadata={"description": 'Financial year, e.g. "2026-27"'})
    period_label = fields.String(
        required=True, metadata={"description": '"Apr 2026", "Q1 2026-27"'}
    )
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    due_date = fields.Date(required=True)
    status = fields.Enum(ComplianceStatus, by_value=True, required=True)
    filing_path = fields.Enum(FilingPath, by_value=True, allow_none=True)


class ItemListArgsSchema(Schema):
    """GET /compliance/items filters (CO4); all optional."""

    status = fields.Enum(ComplianceStatus, by_value=True)
    form_code = fields.Enum(FormCode, by_value=True)
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

    form_code = fields.Enum(FormCode, by_value=True, required=True)
    status = fields.String(required=True, metadata={"description": "TODO, DRAFT or DONE"})
    explanation = fields.String(required=True)
    instructions = fields.String(required=True)
    checklist = fields.List(fields.Nested(ChecklistEntrySchema), required=True)


class TickedChecklistEntrySchema(ChecklistEntrySchema):
    ticked = fields.Boolean(required=True)


class FilingDetailItemSchema(ComplianceItemSchema):
    filed_at = fields.DateTime(allow_none=True)
    acknowledgement_no = fields.String(allow_none=True)


class AcknowledgementSchema(Schema):
    filename = fields.String(required=True)
    uploaded_at = fields.DateTime(required=True)


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

    path = fields.Enum(FilingPath, by_value=True, required=True)


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
