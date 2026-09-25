"""HTTP routes for the assistant module.

URLs: /api/assistant/...  and admin screens under /api/admin/assistant/...
Routes stay thin: parse input (schemas.py), call services.py, return output.
"""

from flask_smorest import Blueprint

blp = Blueprint(
    "assistant",
    __name__,
    url_prefix="/api",
    description="AI assistant: Gemini answers with citations",
)
