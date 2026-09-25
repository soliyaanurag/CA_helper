"""Marshmallow schemas (request/response shapes) for the ca_workspace module."""

from marshmallow import Schema, fields


class CaDashboardSchema(Schema):
    message = fields.String(required=True, metadata={"description": "Welcome text"})
