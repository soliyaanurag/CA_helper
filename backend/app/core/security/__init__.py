"""Security primitives.

Built:
- `passwords.py`: argon2 password hashing (`hash_password`, `verify_password`,
  `needs_rehash`)

Planned:
- `EncryptedString`: a SQLAlchemy column type that Fernet-encrypts values
  (PAN, GSTIN, TAN, phone) using FIELD_ENCRYPTION_KEY
- `blind_index(value)`: HMAC-SHA256 with BLIND_INDEX_KEY, stored next to an
  encrypted column so uniqueness checks and lookups work without decrypting
"""
