"""Request and response shapes for /api/v1/ca-workspace/..."""

from marshmallow import Schema, ValidationError, fields, post_load, validate

from app.models.ca_workspace import DocumentRequestStatus
from app.models.compliance import ComplianceStatus
from app.models.documents import DocumentType
from app.models.enums import FormCode
from app.schemas.compliance import FilingDetailItemSchema, TickedChecklistEntrySchema
from app.schemas.onboarding import MyBusinessSchema


class CaDashboardSchema(Schema):
    message = fields.String(required=True, metadata={"description": "Welcome text"})


class UrgencyReasonSchema(Schema):
    reason = fields.String(required=True, metadata={"description": 'e.g. "2 filing(s) overdue"'})
    points = fields.Integer(required=True)


class CaClientSchema(Schema):
    """One client in "My clients" (CW2), with its urgency (CW6)."""

    business_id = fields.UUID(required=True)
    business_name = fields.String(required=True)
    filing_count = fields.Integer(required=True, metadata={"description": "Engaged filings"})
    open_filing_count = fields.Integer(required=True, metadata={"description": "Not filed yet"})
    open_request_count = fields.Integer(required=True)
    next_deadline = fields.Date(allow_none=True)
    overdue_count = fields.Integer(required=True)
    missing_documents = fields.Integer(required=True)
    score = fields.Integer(required=True, metadata={"description": "Urgency: the sum of points"})
    reasons = fields.List(fields.Nested(UrgencyReasonSchema), required=True)


class DocumentRequestSchema(Schema):
    id = fields.UUID(required=True)
    compliance_item_id = fields.UUID(required=True)
    form_code = fields.Enum(FormCode, by_value=True, allow_none=True)
    period_label = fields.String(allow_none=True)
    checklist_key = fields.String(required=True, metadata={"description": 'or "general"'})
    message = fields.String(required=True)
    status = fields.Enum(DocumentRequestStatus, by_value=True, required=True)
    created_at = fields.DateTime(required=True)
    fulfilled_at = fields.DateTime(allow_none=True)
    document_id = fields.UUID(allow_none=True)


class BusinessDocumentRequestSchema(DocumentRequestSchema):
    ca_name = fields.String(required=True)


class ClientDocumentSchema(Schema):
    document_id = fields.UUID(required=True)
    original_filename = fields.String(required=True)
    doc_type = fields.Enum(DocumentType, by_value=True, required=True)
    size_bytes = fields.Integer(required=True)
    created_at = fields.DateTime(required=True)
    checklist_key = fields.String(
        required=True, metadata={"description": 'A checklist key, "general" or "acknowledgement"'}
    )


class ClientFilingSchema(Schema):
    filing = fields.Nested(FilingDetailItemSchema, required=True)
    checklist = fields.List(fields.Nested(TickedChecklistEntrySchema), required=True)
    documents = fields.List(fields.Nested(ClientDocumentSchema), required=True)
    open_requests = fields.List(fields.Nested(DocumentRequestSchema), required=True)


class CaClientDetailSchema(MyBusinessSchema):
    """GET /ca-workspace/clients/<id> (CW3): the business, its profile and the CA's filings."""

    filings = fields.List(fields.Nested(ClientFilingSchema), required=True)


class BatchFilingSchema(Schema):
    business_id = fields.UUID(required=True)
    business_name = fields.String(required=True)
    compliance_item_id = fields.UUID(required=True)
    period_label = fields.String(required=True)
    status = fields.Enum(ComplianceStatus, by_value=True, required=True)
    required_total = fields.Integer(required=True)
    required_ready = fields.Integer(required=True)
    missing = fields.List(fields.String(), required=True)
    ready = fields.Boolean(required=True)


class BatchSchema(Schema):
    """One form due on one day across clients (CW7)."""

    form_code = fields.Enum(FormCode, by_value=True, required=True)
    due_date = fields.Date(required=True)
    ready_count = fields.Integer(required=True)
    filings = fields.List(fields.Nested(BatchFilingSchema), required=True)


class DocumentRequestCreateSchema(Schema):
    """POST /ca-workspace/clients/<id>/document-requests (CW4)."""

    compliance_item_id = fields.UUID(required=True)
    checklist_key = fields.String(load_default="general", validate=validate.Length(1, 50))
    message = fields.String(required=True, validate=validate.Length(1, 1000))

    @post_load
    def _clean(self, data: dict, **kwargs) -> dict:
        data["message"] = data["message"].strip()
        if not data["message"]:
            raise ValidationError("Write what you need.", "message")
        return data


class DocumentRequestArgsSchema(Schema):
    compliance_item_id = fields.UUID(load_default=None)


class FulfilSchema(Schema):
    """POST /ca-workspace/document-requests/<id>/fulfil."""

    document_id = fields.UUID(required=True)


class CaMarkFiledResultSchema(Schema):
    compliance_item_id = fields.UUID(required=True)
    status = fields.Enum(ComplianceStatus, by_value=True, required=True)
    acknowledgement_no = fields.String(allow_none=True)
    engagement_completed = fields.Boolean(
        required=True, metadata={"description": "True when this was the engagement's last filing"}
    )
