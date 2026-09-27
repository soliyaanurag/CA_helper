"""Request and response shapes for /api/v1/compliance/..."""

from marshmallow import Schema, fields

from app.models.compliance import ComplianceStatus, FilingPath
from app.models.enums import FormCode


class ComplianceDashboardSchema(Schema):
    message = fields.String(required=True, metadata={"description": "Welcome text"})


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
