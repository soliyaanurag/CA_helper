"""Encrypted file storage (owner: Member B). Empty in Phase 0.

Planned (INF-04): save/load uploaded files under UPLOAD_DIR, encrypted at rest
with Fernet. Only metadata (owner, type, period) is stored in the database.
"""
