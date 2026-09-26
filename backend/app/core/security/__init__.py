"""Security primitives.

Built:
- `passwords.py`: argon2 password hashing (`hash_password`, `verify_password`)

Planned:
- `EncryptedString`: a SQLAlchemy column type that Fernet-encrypts values
  (PAN, GSTIN, TAN, phone) with a key from .env (added with this feature)
- `blind_index(value)`: HMAC-SHA256 with BLIND_INDEX_KEY, stored next to an
  encrypted column so uniqueness checks and lookups work without decrypting
"""
