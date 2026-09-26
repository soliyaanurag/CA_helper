"""Password hashing with argon2 (CLAUDE.md rule 4: passwords are hashed, never encrypted).

    password_hash = hash_password("s3cret")
    verify_password(password_hash, "s3cret")   # True / False
    needs_rehash(password_hash)                # True if the argon2 parameters are outdated

argon2-cffi's default parameters are used; when a newer version raises them,
`needs_rehash` becomes true for old hashes and login stores a fresh hash.
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


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
