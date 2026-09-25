"""Authentication: users, login and JWT access tokens.

    models.py    User (the `users` table)
    services.py  authenticate(), get_active_user(), normalize_email()
    tokens.py    access-token contents and JWT error responses
    routes.py    POST /api/v1/auth/login, GET /api/v1/auth/me
    schemas.py   request/response shapes
    seed.py      demo users (one per role) from DEMO_* variables

Role checks for endpoints live in app/core/permissions.py.
Context and contracts: docs/modules/core-auth.md

Planned: signup, email OTP verification, password reset, refresh tokens.
"""
