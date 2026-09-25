"""HTTP routes for the assistant module.

URLs: /api/v1/assistant/...  and admin screens under /api/v1/admin/assistant/...
Routes stay thin: parse input (schemas.py), call one service function, serialize
the result. No queries and no db.session here (docs/PATTERNS.md, "Foundations").
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "assistant",
    __name__,
    description="AI assistant: Gemini answers with citations",
)
