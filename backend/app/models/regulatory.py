"""Regulatory tables: news sources, scraped articles, extracted changes and affected businesses.

    news_sources               a configured site or feed (NewsSource)
    news_articles              one scraped article (NewsArticle)
    regulatory_changes         a change Gemini extracted, waiting for an admin (RegulatoryChange)
    regulatory_change_matches  a business hit by an approved change, N-N (RegulatoryChangeMatch)

Only an approved change is sent to businesses. Article text is public news, never PII.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.enums import FormCode, only_codes, str_enum


class NewsSourceKind(StrEnum):
    RSS = "rss"
    HTML = "html"


class ChangeType(StrEnum):
    DUE_DATE_EXTENSION = "due_date_extension"
    RATE_CHANGE = "rate_change"
    NEW_RULE = "new_rule"
    OTHER = "other"


class RegulatoryChangeStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class NewsSource(BaseModel):
    """A news site or official update page we scrape (switched off with `enabled`)."""

    __tablename__ = "news_sources"

    name: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(500), unique=True)
    kind: Mapped[NewsSourceKind] = mapped_column(str_enum(NewsSourceKind))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class NewsArticle(BaseModel):
    """One scraped article; `content_hash` stops the same text being stored twice."""

    __tablename__ = "news_articles"

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("news_sources.id"), index=True)
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)  # SHA-256 of content


class RegulatoryChange(BaseModel):
    """A deadline or rule change extracted from an article, reviewed by an admin."""

    __tablename__ = "regulatory_changes"
    __table_args__ = (only_codes("form_codes", [code.value for code in FormCode]),)

    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("news_articles.id"), index=True)
    change_type: Mapped[ChangeType] = mapped_column(str_enum(ChangeType))
    summary: Mapped[str] = mapped_column(Text)
    # The forms it affects, e.g. {gstr_3b}: an array of FormCode values.
    form_codes: Mapped[list[str]] = mapped_column(ARRAY(String(50)))
    # Who it affects, e.g. {"gst_scheme": ["regular_monthly"], "states": ["Maharashtra"]}.
    affected_categories: Mapped[dict] = mapped_column(JSONB)
    # The dates it mentions, e.g. {"old_due_date": "2026-10-20", "new_due_date": "2026-10-31"}.
    dates: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[RegulatoryChangeStatus] = mapped_column(
        str_enum(RegulatoryChangeStatus), default=RegulatoryChangeStatus.PENDING
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class RegulatoryChangeMatch(BaseModel):
    """A business affected by an approved change (at most once per change)."""

    __tablename__ = "regulatory_change_matches"
    __table_args__ = (UniqueConstraint("change_id", "business_id"),)

    change_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("regulatory_changes.id"))
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
