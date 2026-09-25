"""Request and response shapes for /api/v1/auth/..."""

from marshmallow import Schema, fields, validate

from app.core.db.enums import UserRole


class LoginSchema(Schema):
    # Not fields.Email: the service trims and lowercases, and a malformed email
    # simply matches no user (401), like any unknown one.
    email = fields.String(required=True, validate=validate.Length(1, 254))
    # A maximum keeps a huge password from tying up argon2.
    password = fields.String(required=True, load_only=True, validate=validate.Length(1, 128))


class UserSchema(Schema):
    id = fields.UUID(required=True)
    email = fields.String(required=True)
    full_name = fields.String(required=True)
    role = fields.Enum(UserRole, by_value=True, required=True)


class LoginResponseSchema(Schema):
    access_token = fields.String(required=True)
    user = fields.Nested(UserSchema, required=True)
