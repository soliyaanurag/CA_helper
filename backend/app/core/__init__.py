"""Shared building blocks used by every feature module.

    auth/, permissions.py   authentication and access control
    db/                     Base, BaseModel + mixins, str_enum()
    security/               password hashing
    errors.py, health.py    JSON error format, GET /api/health

Planned packages (created with the feature that needs them; see
docs/modules/core-infra.md): ai/ (gemini_client.py), email/, notifications/,
ocr/, storage/.

Every module depends on this package, so a change here must be called out clearly in the PR.
"""
