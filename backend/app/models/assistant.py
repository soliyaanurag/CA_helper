"""Assistant tables: the knowledge base for retrieval, and chat history.

    kb_chunks      a piece of our own content or an official FAQ, with its embedding (KbChunk)
    chat_messages  one message of a user's conversation with the assistant (ChatMessage)

Embeddings are vector(768) from the pgvector extension. kb_chunks holds public content
only (no user data), so it has no foreign keys. Nothing with PII goes to Gemini (rule 1).
"""

import uuid
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.enums import str_enum

EMBEDDING_SIZE = 768


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class KbChunk(BaseModel):
    """One chunk of a knowledge-base source, e.g. content/forms/GSTR-3B/explanation.md part 2."""

    __tablename__ = "kb_chunks"
    __table_args__ = (UniqueConstraint("source_path", "chunk_index"),)

    source_path: Mapped[str] = mapped_column(String(300))  # repo path or FAQ identifier
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(1000))  # the official page, for citations
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_SIZE))


class ChatMessage(BaseModel):
    """One message in a user's assistant conversation (deleted when cleared)."""

    __tablename__ = "chat_messages"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[ChatRole] = mapped_column(str_enum(ChatRole))
    content: Mapped[str] = mapped_column(Text)
    # For an answer: {"sources": [{number, title, url, source_path, excerpt}], "ask_a_ca": bool,
    # "ai_used": bool} (assistant_service.ask). Empty for a question.
    citations: Mapped[dict | None] = mapped_column(JSONB)
