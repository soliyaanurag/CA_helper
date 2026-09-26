"""Request and response shapes for /api/v1/auth/..."""

import re

from marshmallow import Schema, ValidationError, fields, validate

from app.models.enums import UserRole

# The password rule. The frontend checks the same rule (frontend/src/lib/passwords.js).
PASSWORD_MIN_LENGTH = 8
# A maximum keeps a huge password from tying up argon2.
PASSWORD_MAX_LENGTH = 128
PASSWORD_RULE_TEXT = "Use 8 to 128 characters, with at least one letter and one number."


def validate_new_password(value: str) -> None:
    """Every password we store must follow the rule (signup, reset, change)."""
    if not (
        PASSWORD_MIN_LENGTH <= len(value) <= PASSWORD_MAX_LENGTH
        and re.search(r"[A-Za-z]", value)
        and re.search(r"[0-9]", value)
    ):
        raise ValidationError(PASSWORD_RULE_TEXT)


def _not_blank(value: str) -> None:
    if not value.strip():
        raise ValidationError("Must not be blank.")


def _email_field() -> fields.String:
    # Not fields.Email: the service trims and lowercases, and a malformed email
    # simply matches no user, like any unknown one.
    return fields.String(required=True, validate=validate.Length(1, 254))


def _new_password_field() -> fields.String:
    return fields.String(required=True, load_only=True, validate=validate_new_password)


def _code_field() -> fields.String:
    return fields.String(
        required=True, validate=validate.Regexp(r"^[0-9]{6}$", error="Enter the 6-digit code.")
    )


class LoginSchema(Schema):
    email = _email_field()
    password = fields.String(
        required=True, load_only=True, validate=validate.Length(1, PASSWORD_MAX_LENGTH)
    )


class UserSchema(Schema):
    id = fields.UUID(required=True)
    email = fields.String(required=True)
    full_name = fields.String(required=True)
    role = fields.Enum(UserRole, by_value=True, required=True)


class LoginResponseSchema(Schema):
    access_token = fields.String(required=True)
    user = fields.Nested(UserSchema, required=True)


class SignupSchema(Schema):
    full_name = fields.String(required=True, validate=[validate.Length(1, 200), _not_blank])
    # A real email format here: this one is stored.
    email = fields.Email(required=True, validate=validate.Length(max=254))
    password = _new_password_field()
    # Only businesses and CAs sign up; admins are created by `flask seed` or an admin.
    role = fields.Enum(
        UserRole,
        by_value=True,
        required=True,
        validate=validate.OneOf([UserRole.BUSINESS, UserRole.CA], error="Choose business or ca."),
    )


class AuthEmailSchema(Schema):
    """Just an email: resend the verification code, forgot password."""

    email = _email_field()


class VerifyEmailSchema(Schema):
    email = _email_field()
    code = _code_field()


class ResetPasswordSchema(Schema):
    email = _email_field()
    code = _code_field()
    new_password = _new_password_field()


class ChangePasswordSchema(Schema):
    current_password = fields.String(
        required=True, load_only=True, validate=validate.Length(1, PASSWORD_MAX_LENGTH)
    )
    new_password = _new_password_field()
