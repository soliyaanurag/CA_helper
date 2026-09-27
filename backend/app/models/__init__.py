"""Database models (SQLAlchemy), one file per table or group of related tables.

    base.py       BaseModel (UUID id + timestamps), SoftDeleteMixin, utcnow()
    enums.py      str_enum() and the enums shared by several models (UserRole)
    user.py       User (`users`)
    email_otp.py  EmailOtp (`email_otps`): emailed one-time codes, OtpPurpose
    marketplace.py  CaProfile (`ca_profiles`), CatalogService (`service_catalog`),
                    CaService (`ca_services`): CA profiles, the service catalog, CA prices

Every model is imported here, so Alembic (`make migration`) sees every table.
Import a new model here when you add its file.
"""

from app.models.email_otp import EmailOtp
from app.models.marketplace import CaProfile, CaService, CatalogService
from app.models.user import User

__all__ = ["CaProfile", "CaService", "CatalogService", "EmailOtp", "User"]
