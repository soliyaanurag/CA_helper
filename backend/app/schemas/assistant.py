"""Request and response shapes for /api/v1/assistant/..."""

from marshmallow import Schema, fields, validate

from app.models.assistant import ChatRole


class QuestionSchema(Schema):
    """POST /assistant/ask. Do not type personal details: they are removed before Gemini."""

    question = fields.String(required=True, validate=validate.Length(3, 500))


class CitationSchema(Schema):
    """One source an answer used: our guide or an official FAQ page."""

    number = fields.Integer(required=True, metadata={"description": "The [n] in the answer"})
    title = fields.String(required=True)
    url = fields.String(allow_none=True, metadata={"description": "The official page, if any"})
    source_path = fields.String(required=True, metadata={"description": "e.g. content/faqs/..."})
    excerpt = fields.String(required=True, metadata={"description": "The start of the passage"})


class AnswerSchema(Schema):
    answer = fields.String(required=True)
    citations = fields.List(fields.Nested(CitationSchema), required=True)
    ask_a_ca = fields.Boolean(required=True, metadata={"description": "Suggest the marketplace"})
    ai_used = fields.Boolean(required=True, metadata={"description": "False: passages only"})


class ChatMessageSchema(Schema):
    id = fields.UUID(required=True)
    role = fields.String(validate=validate.OneOf(list(ChatRole)), required=True)
    content = fields.String(required=True)
    citations = fields.List(fields.Nested(CitationSchema), required=True)
    ask_a_ca = fields.Boolean(required=True)
    ai_used = fields.Boolean(required=True)
    created_at = fields.DateTime(required=True)
