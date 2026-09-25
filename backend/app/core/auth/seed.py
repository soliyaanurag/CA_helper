"""Demo users for development: one per role, from DEMO_* variables in .env.

    DEMO_BUSINESS_EMAIL / DEMO_BUSINESS_PASSWORD
    DEMO_CA_EMAIL       / DEMO_CA_PASSWORD
    DEMO_ADMIN_EMAIL    / DEMO_ADMIN_PASSWORD

A role whose variables are empty is skipped with a warning. An existing user
(same email) is left untouched, so re-running is safe. Does not commit
(run_all_seeds() commits once).
"""

import logging
import os

from sqlalchemy import select

from app.core.auth.models import User
from app.core.auth.services import normalize_email
from app.core.db.enums import UserRole
from app.core.security.passwords import hash_password
from app.extensions import db

log = logging.getLogger(__name__)

DEMO_NAMES = {
    UserRole.BUSINESS: "Demo Business Owner",
    UserRole.CA: "Demo CA",
    UserRole.ADMIN: "Demo Admin",
}


def seed() -> None:
    for role, full_name in DEMO_NAMES.items():
        prefix = f"DEMO_{role.value.upper()}"
        email = normalize_email(os.getenv(f"{prefix}_EMAIL", ""))
        password = os.getenv(f"{prefix}_PASSWORD", "")
        if not email or not password:
            log.warning("Skipping demo %s user: set %s_EMAIL and %s_PASSWORD", role, prefix, prefix)
            continue
        if db.session.scalar(select(User.id).where(User.email == email)):
            continue
        db.session.add(
            User(email=email, password_hash=hash_password(password), full_name=full_name, role=role)
        )
        log.info("Added demo %s user", role)
