"""Marshmallow schemas (request/response shapes) for the admin module."""

from marshmallow import Schema, fields


class AdminDashboardSchema(Schema):
    message = fields.String(required=True, metadata={"description": "Welcome text"})
