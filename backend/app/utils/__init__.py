"""Shared helpers used by routes and services.

    decorators.py    roles_required / login_required / current_user (access control)
    email.py         send_email(): plain-text email from app/templates/email/
    encryption.py    EncryptedString: Fernet-encrypted text columns (PAN, GSTIN, TAN, phone)
    jwt_handlers.py  JWT user loading and token error responses
    passwords.py     argon2 hash_password / verify_password

Planned (docs/modules/core-infra.md): gemini_client.py (the only way to call
Gemini, scrubs PII), storage.py (encrypted uploads), ocr.py (local Tesseract).
"""
