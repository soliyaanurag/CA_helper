"""Encrypted columns (CLAUDE.md rule 4): PAN, GSTIN, TAN and phone.

    pan: Mapped[str] = mapped_column(EncryptedString())

The value is encrypted with Fernet (from the `cryptography` package) before it is
written, and decrypted when it is read, so the rest of the code sees plain text while
the database only holds tokens like "gAAAAAB...". The key is FIELD_ENCRYPTION_KEY
from .env; losing it makes the stored values unreadable.

Fernet adds a random part to every token, so the same PAN encrypts differently each
time: an encrypted column cannot be searched (WHERE pan = ...) or made UNIQUE. That is
accepted: we never look businesses up by PAN, GSTIN or TAN (docs/DECISIONS.md).
"""

from functools import cache

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

KEY_HELP = (
    "Generate one with:\n"
    "  conda run -n ca-helper python -c "
    '"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"\n'
    "and put it in .env as FIELD_ENCRYPTION_KEY=... (see .env.example)."
)


@cache
def _fernet_for(key: str) -> Fernet:
    try:
        return Fernet(key)
    except ValueError as error:
        raise RuntimeError(f"FIELD_ENCRYPTION_KEY is not a valid Fernet key. {KEY_HELP}") from error


def _fernet() -> Fernet:
    key = current_app.config.get("FIELD_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(f"FIELD_ENCRYPTION_KEY is not set. {KEY_HELP}")
    return _fernet_for(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt a file's contents (app/utils/storage.py)."""
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _fernet().decrypt(token)
    except InvalidToken as error:
        raise RuntimeError(
            "A stored file cannot be decrypted: FIELD_ENCRYPTION_KEY is not the key it was "
            "encrypted with."
        ) from error


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as error:
        raise RuntimeError(
            "An encrypted value cannot be decrypted: FIELD_ENCRYPTION_KEY is not the key it was "
            "encrypted with."
        ) from error


class EncryptedString(TypeDecorator):
    """A text column stored encrypted. None stays None (NULL)."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt(value)

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt(value)
