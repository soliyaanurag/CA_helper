"""Authentication. Not built yet.

Planned:
- signup/login for businesses and CAs; seeded admin account
- JWT access + refresh tokens carrying a `role` claim (business | ca | admin)
- loading the current user from the token
- email OTP verification and password reset
- JWT error callbacks returning the standard error format (app/core/errors.py)
"""
