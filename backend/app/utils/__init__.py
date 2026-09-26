"""Shared helpers used by routes and services.

    decorators.py    roles_required / login_required / current_user (access control)
    jwt_handlers.py  JWT user loading and token error responses
    passwords.py     argon2 hash_password / verify_password
    logging_setup.py log format (text/JSON) and X-Request-ID handling

Planned (docs/modules/core-infra.md): gemini_client.py (the only way to call
Gemini, scrubs PII), encryption.py (EncryptedString, blind index), storage.py
(encrypted uploads), ocr.py (local Tesseract), email.py.
"""
