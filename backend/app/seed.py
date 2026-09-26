"""Development seed data and the `flask seed` command (make seed).

Demo users, one per role, come from DEMO_* variables in .env:

    DEMO_BUSINESS_EMAIL / DEMO_BUSINESS_PASSWORD
    DEMO_CA_EMAIL       / DEMO_CA_PASSWORD
    DEMO_ADMIN_EMAIL    / DEMO_ADMIN_PASSWORD

A role whose variables are empty is skipped with a warning. Every seed function
must be safe to re-run (it skips rows that already exist) and must not commit:
run_all_seeds() commits once at the end. Add a new table's seed function to SEEDS.
"""

import logging
import os

import click
from flask import Flask
from sqlalchemy import select

from app.extensions import db
from app.models import User
from app.models.enums import UserRole
from app.services.auth_service import normalize_email
from app.utils.passwords import hash_password

log = logging.getLogger(__name__)

DEMO_NAMES = {
    UserRole.BUSINESS: "Demo Business Owner",
    UserRole.CA: "Demo CA",
    UserRole.ADMIN: "Demo Admin",
}


def seed_demo_users() -> None:
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


# (name, function) in dependency order: users first, other data may refer to them.
SEEDS = [
    ("demo users", seed_demo_users),
]


def run_all_seeds() -> list[str]:
    """Run every seed function, then commit once. Returns the names that ran."""
    for _, seed in SEEDS:
        seed()
    db.session.commit()
    return [name for name, _ in SEEDS]


def register_commands(app: Flask) -> None:
    @app.cli.command("seed")
    def seed_command() -> None:
        """Insert development seed data. Safe to re-run."""
        click.echo(f"Seeded: {', '.join(run_all_seeds())}")
