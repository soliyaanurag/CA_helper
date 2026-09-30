"""Request and response shapes for /api/v1/documents/..."""

import re

from marshmallow import Schema, ValidationError, fields, post_load, validate

from app.models.documents import DocumentType, OcrStatus
from app.models.enums import FormCode
from app.schemas.pagination import PageArgsSchema, PageSchema

# A financial year is written "2026-27": April 2026 to March 2027.
FY_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


def _check_fy(value: str) -> None:
    match = FY_PATTERN.match(value)
    if match is None or (int(match.group(1)) + 1) % 100 != int(match.group(2)):
        raise ValidationError('Write the financial year like "2026-27".')


class DocumentLinkSchema(Schema):
    id = fields.UUID(required=True, metadata={"description": "The link's id (to unlink it)"})
    compliance_item_id = fields.UUID(required=True)
    form_code = fields.String(validate=validate.OneOf(list(FormCode)), required=True)
    period_label = fields.String(required=True)
    checklist_key = fields.String(required=True, metadata={"description": 'or "general"'})


class AcknowledgedFilingSchema(Schema):
    compliance_item_id = fields.UUID(required=True)
    form_code = fields.String(validate=validate.OneOf(list(FormCode)), required=True)
    period_label = fields.String(required=True)


class DocumentSchema(Schema):
    id = fields.UUID(required=True)
    doc_type = fields.String(validate=validate.OneOf(list(DocumentType)), required=True)
    original_filename = fields.String(required=True)
    mime_type = fields.String(required=True)
    size_bytes = fields.Integer(required=True)
    fy = fields.String(allow_none=True, metadata={"description": 'e.g. "2026-27"'})
    period_label = fields.String(allow_none=True, metadata={"description": 'e.g. "Apr 2026"'})
    ocr_status = fields.String(validate=validate.OneOf(list(OcrStatus)), required=True)
    type_warning = fields.String(
        allow_none=True,
        metadata={"description": "What the file looks like when it differs from doc_type (DO9)"},
    )
    created_at = fields.DateTime(required=True)
    links = fields.List(
        fields.Nested(DocumentLinkSchema),
        required=True,
        metadata={"description": "The filings (and checklist entries) this file serves"},
    )
    acknowledgement_of = fields.List(
        fields.Nested(AcknowledgedFilingSchema),
        required=True,
        metadata={"description": "The filings this file is the acknowledgement of"},
    )


class DocumentPageSchema(PageSchema):
    items = fields.List(fields.Nested(DocumentSchema), required=True)


class DocumentListArgsSchema(PageArgsSchema):
    fy = fields.String(load_default=None, validate=_check_fy)
    doc_type = fields.String(validate=validate.OneOf(list(DocumentType)), load_default=None)
    compliance_item_id = fields.UUID(
        load_default=None, metadata={"description": "Only the documents of this filing"}
    )


class DocumentUploadFormSchema(Schema):
    """POST /documents (multipart/form-data), the text part."""

    doc_type = fields.String(
        required=True,
        validate=[
            validate.OneOf(list(DocumentType)),
            validate.NoneOf(
                [DocumentType.CERTIFICATE_OF_PRACTICE], error="This type cannot be uploaded here."
            ),
        ],
    )
    fy = fields.String(load_default=None, validate=_check_fy)
    period_label = fields.String(load_default=None, validate=validate.Length(max=30))
    compliance_item_id = fields.UUID(
        load_default=None, metadata={"description": "Also link the file to this filing"}
    )
    checklist_key = fields.String(
        load_default=None,
        validate=validate.Length(1, 50),
        metadata={"description": 'The checklist entry it answers (default "general")'},
    )

    @post_load
    def _clean(self, data: dict, **kwargs) -> dict:
        if data["period_label"] is not None:
            data["period_label"] = data["period_label"].strip() or None
        return data


class DocumentUploadFileSchema(Schema):
    """The file (PDF, JPG or PNG)."""

    file = fields.Raw(required=True, metadata={"type": "string", "format": "binary"})


class DocumentLinkCreateSchema(Schema):
    """POST /documents/<id>/links."""

    compliance_item_id = fields.UUID(required=True)
    checklist_key = fields.String(
        load_default="general",
        validate=validate.Length(1, 50),
        metadata={"description": 'The checklist entry it answers, or "general"'},
    )
