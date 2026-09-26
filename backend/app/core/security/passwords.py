"""Password hashing with argon2 (CLAUDE.md rule 4: passwords are hashed, never encrypted).

    password_hash = hash_password("s3cret")
    verify_password(password_hash, "s3cret")   # True / False

argon2-cffi's default parameters are used.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """True if `password` matches the stored hash. Never raises for a wrong password."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
