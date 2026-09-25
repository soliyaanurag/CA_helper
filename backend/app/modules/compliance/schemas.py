"""Marshmallow schemas (request/response shapes) for the compliance module."""

from marshmallow import Schema, fields


class ComplianceDashboardSchema(Schema):
    message = fields.String(required=True, metadata={"description": "Welcome text"})
