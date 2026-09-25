"""Business logic for core/auth: checking passwords and loading users.

Service functions other code calls (docs/modules/core-auth.md):
    authenticate(email, password) -> User       login
    get_active_user(user_id) -> User | None     used by the JWT user loader
    normalize_email(email) -> str

Each public function that changes data commits once at its end (docs/PATTERNS.md).
"""

import logging
import uuid
from functools import cache

from sqlalchemy import select

from app.core.auth.models import User
from app.core.errors import ApiError
from app.core.security.passwords import hash_password, needs_rehash, verify_password
from app.extensions import db

log = logging.getLogger(__name__)


def normalize_email(email: str) -> str:
    """Emails are stored and compared trimmed and lowercased."""
    return email.strip().lower()


@cache
def _dummy_hash() -> str:
    """A real argon2 hash of a random value, computed once.

    Checked when the email is unknown, so an unknown email takes as long as a
    wrong password and the response time does not reveal which emails exist.
    """
    return hash_password(uuid.uuid4().hex)


def authenticate(email: str, password: str) -> User:
    """Return the user for these credentials, or raise ApiError.

    401 INVALID_CREDENTIALS for an unknown email or a wrong password (the same
    error for both); 403 ACCOUNT_INACTIVE for a deactivated or deleted account.
    Rehashes the password if argon2's parameters changed since it was stored.
    """
    user = db.session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        verify_password(_dummy_hash(), password)
        raise ApiError(401, "INVALID_CREDENTIALS", "Wrong email or password.")
    if not verify_password(user.password_hash, password):
        raise ApiError(401, "INVALID_CREDENTIALS", "Wrong email or password.")
    if not user.is_active or user.deleted_at is not None:
        raise ApiError(403, "ACCOUNT_INACTIVE", "This account is inactive.")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        log.info("Rehashed password for user %s", user.id)
    db.session.commit()
    log.info("User %s logged in", user.id)
    return user


def get_active_user(user_id: str) -> User | None:
    """The user with this id if they may still use the app (active, not deleted), else None."""
    try:
        key = uuid.UUID(user_id)
    except (TypeError, ValueError):
        return None
    user = db.session.get(User, key)
    if user is None or not user.is_active or user.deleted_at is not None:
        return None
    return user
