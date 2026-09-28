"""Routes for the AI assistant (all under /api/v1), for business owners and CAs.

    POST   /api/v1/assistant/ask       ask a question: an answer with its sources (AS2-AS4)
    GET    /api/v1/assistant/history   the user's past questions and answers (AS5)
    DELETE /api/v1/assistant/history   clear them

    flask assistant ingest             build / refresh the knowledge base from content/ (AS1)

Each route only checks who is calling, reads the input, calls one function in
app/services/assistant_service.py and returns its result as JSON.
"""

import click
from flask_smorest import Blueprint

from app.errors import ErrorSchema
from app.extensions import limiter
from app.models.enums import UserRole
from app.schemas.assistant import AnswerSchema, ChatMessageSchema, QuestionSchema
from app.services import assistant_service
from app.utils.decorators import current_user, roles_required

blp = Blueprint("assistant", __name__, description="AI assistant with sources")


# Ask a question. The answer cites our guides and official FAQs; no personal data goes to Gemini.
@blp.route("/assistant/ask", methods=["POST"])
@limiter.limit("10 per minute")
@roles_required(UserRole.BUSINESS, UserRole.CA)
@blp.arguments(QuestionSchema)
@blp.response(200, AnswerSchema)
@blp.alt_response(429, schema=ErrorSchema, description="TOO_MANY_REQUESTS (rate limit per IP)")
def ask(data):
    return assistant_service.ask(current_user(), data["question"])


# The user's conversation, oldest first.
@blp.route("/assistant/history", methods=["GET"])
@roles_required(UserRole.BUSINESS, UserRole.CA)
@blp.response(200, ChatMessageSchema(many=True))
def history():
    return assistant_service.list_history(current_user())


# Clear the conversation.
@blp.route("/assistant/history", methods=["DELETE"])
@roles_required(UserRole.BUSINESS, UserRole.CA)
@blp.response(204)
def clear_history():
    assistant_service.clear_history(current_user())


# `flask assistant ingest` (make assistant-ingest): build the knowledge base. Needs GEMINI_API_KEY.
@blp.cli.command("ingest")
def ingest_command():
    """Read content/forms and content/faqs, embed new or changed chunks, save them."""
    counts = assistant_service.ingest_knowledge()
    click.echo(
        f"Knowledge base: {counts['chunks']} chunks ({counts['embedded']} embedded now, "
        f"{counts['removed']} removed)."
    )
