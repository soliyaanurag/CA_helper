"""Request and response shapes for /api/v1/admin/..."""

from marshmallow import Schema, fields, validate

from app.models.enums import UserRole
from app.models.marketplace import CaVerificationStatus
from app.schemas.pagination import PageArgsSchema, PageSchema


class AdminDashboardSchema(Schema):
    message = fields.String(required=True, metadata={"description": "Welcome text"})


class AdminStatsSchema(Schema):
    users_by_role = fields.Dict(keys=fields.String(), values=fields.Integer(), required=True)
    businesses = fields.Integer(required=True)
    cas_by_status = fields.Dict(keys=fields.String(), values=fields.Integer(), required=True)
    open_engagements = fields.Integer(required=True)
    filings_by_status = fields.Dict(
        keys=fields.String(),
        values=fields.Integer(),
        required=True,
        metadata={"description": "AD5"},
    )
    filings_due_so_far = fields.Integer(required=True, metadata={"description": "Due date passed"})
    filings_late = fields.Integer(
        required=True, metadata={"description": "Of those: not filed, or filed after the due date"}
    )
    overdue_rate = fields.Float(
        allow_none=True, metadata={"description": "filings_late / filings_due_so_far, in percent"}
    )


class AdminUserArgsSchema(PageArgsSchema):
    role = fields.String(validate=validate.OneOf(list(UserRole)))
    search = fields.String(validate=validate.Length(max=100))


class AdminUserSchema(Schema):
    id = fields.UUID(required=True)
    full_name = fields.String(required=True)
    email = fields.String(required=True)
    role = fields.String(validate=validate.OneOf(list(UserRole)), required=True)
    email_verified = fields.Function(lambda user: user.email_verified_at is not None)
    created_at = fields.DateTime(required=True)


class AdminUserPageSchema(PageSchema):
    items = fields.List(fields.Nested(AdminUserSchema), required=True)


class AdminCaArgsSchema(Schema):
    status = fields.String(validate=validate.OneOf(list(CaVerificationStatus)))


class AdminCaSchema(Schema):
    """A CA profile with everything an admin checks (including the CoP number)."""

    id = fields.UUID(required=True)
    user_id = fields.UUID(required=True)
    full_name = fields.String(required=True)
    email = fields.String(required=True)
    membership_no = fields.String(required=True)
    cop_number = fields.String(required=True)
    city = fields.String(required=True)
    languages = fields.List(fields.String(), required=True)
    specializations = fields.List(fields.String(), required=True)
    capacity = fields.Integer(required=True)
    years_experience = fields.Integer(required=True)
    pro_bono_slots_per_month = fields.Integer(required=True)
    about = fields.String(required=True)
    verification_status = fields.String(validate=validate.OneOf(list(CaVerificationStatus)), required=True)
    rejection_reason = fields.String(allow_none=True)
    verified_at = fields.DateTime(allow_none=True)
    has_certificate = fields.Boolean(required=True)
    updated_at = fields.DateTime(required=True)


def _not_blank(value: str) -> None:
    if not value.strip():
        raise validate.ValidationError("Give a reason.")


class RejectCaInputSchema(Schema):
    reason = fields.String(required=True, validate=[validate.Length(1, 500), _not_blank])
