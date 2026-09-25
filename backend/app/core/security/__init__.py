"""Security primitives. Not built yet.

Planned:
- `EncryptedString`: a SQLAlchemy column type that Fernet-encrypts values
  (PAN, GSTIN, TAN, phone) using FIELD_ENCRYPTION_KEY
- `blind_index(value)`: HMAC-SHA256 with BLIND_INDEX_KEY, stored next to an
  encrypted column so uniqueness checks and lookups work without decrypting
- password hashing with argon2 (passwords are hashed, never encrypted)
"""
