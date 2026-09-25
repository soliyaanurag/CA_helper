"""Authentication (owner: Member A). Empty in Phase 0.

Planned (AUTH-01, AUTH-02, AUTH-05):
- signup/login for businesses and CAs; seeded admin (AUTH-04)
- JWT access + refresh tokens carrying a `role` claim (business | ca | admin)
- loading the current user from the token
- email OTP verification and password reset
- JWT error callbacks returning the standard error format (app/core/errors.py)
"""
