"""Assistant module: AI assistant: Gemini answers with citations.

Owner: Member B. Tasks and contracts: docs/modules/assistant.md
Discovered automatically by app/modules/__init__.py.
"""

from app.modules.assistant.routes import blp
from app.modules.assistant.seed import seed

__all__ = ["blp", "seed"]
