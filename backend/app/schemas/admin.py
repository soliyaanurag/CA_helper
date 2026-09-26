"""Request and response shapes for /api/v1/admin/..."""

from marshmallow import Schema, fields


class AdminDashboardSchema(Schema):
    message = fields.String(required=True, metadata={"description": "Welcome text"})
