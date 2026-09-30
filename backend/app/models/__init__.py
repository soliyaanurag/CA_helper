"""Database models (SQLAlchemy): one file per module (docs/DATA_MODEL.md has every table).

    base.py          BaseModel (UUID id + timestamps), utcnow()
    enums.py         the shared enums (UserRole, FormCode)
    user.py          core-auth: User (`users`)
    email_otp.py     core-auth: EmailOtp (`email_otps`), OtpPurpose
    onboarding.py    Business, RegulatoryProfile, NicCode, RuleThreshold
    compliance.py    ObligationTemplate, ComplianceItem, ChecklistTick
    documents.py     Document, ComplianceItemDocument
    alerts.py        Notification, NotificationSetting, ReminderLog, PenaltyRule
    marketplace.py   CaProfile, CatalogService, CaService, Engagement, EngagementItem, Rating,
                     ProBonoRequest
    ca_workspace.py  DocumentRequest
    regulatory.py    NewsSource, NewsArticle, RegulatoryChange, RegulatoryChangeMatch
    assistant.py     KbChunk, ChatMessage

Every model is imported here, so Alembic (`make migration`) sees every table.
Import a new model here when you add its file.
"""

from app.models.alerts import Notification, NotificationSetting, PenaltyRule, ReminderLog
from app.models.assistant import ChatMessage, KbChunk
from app.models.ca_workspace import DocumentRequest
from app.models.compliance import ChecklistTick, ComplianceItem, ObligationTemplate
from app.models.documents import ComplianceItemDocument, Document
from app.models.email_otp import EmailOtp
from app.models.marketplace import (
    CaProfile,
    CaService,
    CatalogService,
    Engagement,
    EngagementItem,
    ProBonoRequest,
    Rating,
)
from app.models.onboarding import Business, NicCode, RegulatoryProfile, RuleThreshold
from app.models.regulatory import (
    NewsArticle,
    NewsSource,
    RegulatoryChange,
    RegulatoryChangeMatch,
)
from app.models.user import User

__all__ = [
    "Business",
    "CaProfile",
    "CaService",
    "CatalogService",
    "ChatMessage",
    "ChecklistTick",
    "ComplianceItem",
    "ComplianceItemDocument",
    "Document",
    "DocumentRequest",
    "EmailOtp",
    "Engagement",
    "EngagementItem",
    "KbChunk",
    "NewsArticle",
    "NewsSource",
    "NicCode",
    "Notification",
    "NotificationSetting",
    "ObligationTemplate",
    "PenaltyRule",
    "ProBonoRequest",
    "Rating",
    "RegulatoryChange",
    "RegulatoryChangeMatch",
    "RegulatoryProfile",
    "ReminderLog",
    "RuleThreshold",
    "User",
]
