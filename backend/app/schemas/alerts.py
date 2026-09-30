"""Request and response shapes for /api/v1/alerts/..."""

from marshmallow import Schema, fields, validate

from app.models.alerts import NotificationType
from app.models.enums import FormCode
from app.schemas.pagination import PageArgsSchema, PageSchema
from app.services.alerts_service import CONFIGURABLE_TYPES


class NotificationSchema(Schema):
    id = fields.UUID(required=True)
    type = fields.String(validate=validate.OneOf(list(NotificationType)), required=True)
    title = fields.String(required=True)
    body = fields.String(required=True)
    link = fields.String(allow_none=True, metadata={"description": "An app path, or null"})
    read_at = fields.DateTime(allow_none=True)
    created_at = fields.DateTime(required=True)


class NotificationPageSchema(PageSchema):
    items = fields.List(fields.Nested(NotificationSchema), required=True)


class NotificationArgsSchema(PageArgsSchema):
    pass


class UnreadCountSchema(Schema):
    unread = fields.Integer(required=True)


class NotificationSettingSchema(Schema):
    type = fields.String(
        required=True,
        validate=validate.OneOf(CONFIGURABLE_TYPES, error="Emails of this type are always sent."),
    )
    email_enabled = fields.Boolean(required=True)


class NotificationSettingsSchema(Schema):
    items = fields.List(fields.Nested(NotificationSettingSchema), required=True)
    always_emailed = fields.List(
        fields.String(validate=validate.OneOf(list(NotificationType))),
        dump_only=True,
        metadata={"description": "Types that are always emailed (no switch)"},
    )


class PenaltyArgsSchema(Schema):
    tax_due = fields.Decimal(
        places=2,
        validate=validate.Range(min=0, max=10**10),
        metadata={"description": "Unpaid tax in rupees, to estimate the interest"},
    )


class PenaltyEstimateSchema(Schema):
    compliance_item_id = fields.UUID(required=True)
    form_code = fields.String(validate=validate.OneOf(list(FormCode)), required=True)
    period_label = fields.String(required=True)
    due_date = fields.Date(required=True)
    days_late = fields.Integer(required=True)
    status = fields.String(
        required=True, metadata={"description": "not_late, filed, estimated or pending"}
    )
    late_fee = fields.Decimal(as_string=True, places=2, allow_none=True)
    interest = fields.Decimal(as_string=True, places=2, allow_none=True)
    total = fields.Decimal(as_string=True, places=2, allow_none=True)
    notes = fields.List(fields.String(), required=True, metadata={"description": "What is missing"})
    label = fields.String(required=True)


class PenaltyExposureSchema(Schema):
    total_late_fees = fields.Decimal(as_string=True, places=2, required=True)
    overdue_count = fields.Integer(required=True)
    estimated_count = fields.Integer(required=True)
    pending_count = fields.Integer(required=True)
    label = fields.String(required=True)
    items = fields.List(fields.Nested(PenaltyEstimateSchema), required=True)
