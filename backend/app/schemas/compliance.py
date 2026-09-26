"""Request and response shapes for /api/v1/compliance/..."""

from marshmallow import Schema, fields


class ComplianceDashboardSchema(Schema):
    message = fields.String(required=True, metadata={"description": "Welcome text"})
