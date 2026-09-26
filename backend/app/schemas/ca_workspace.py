"""Request and response shapes for /api/v1/ca-workspace/..."""

from marshmallow import Schema, fields


class CaDashboardSchema(Schema):
    message = fields.String(required=True, metadata={"description": "Welcome text"})
