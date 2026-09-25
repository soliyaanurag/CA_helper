# core-auth: authentication and access control

## Purpose
Users, signup/login for businesses and CAs, JWT access/refresh tokens with a role claim, email OTP, password reset, the seeded admin, and the shared access-control helpers (`core/permissions.py`).

## What exists now
Nothing functional yet.
- `backend/app/core/auth/__init__.py` and `backend/app/core/permissions.py` contain only docstrings describing the plan.
- flask-jwt-extended (`JWTManager`) and Flask-Limiter are initialised in `app/extensions.py` (JWT secret from `JWT_SECRET_KEY`), but no token is issued, no endpoint is protected and no rate limit is set.
- Frontend: no auth pages, no auth context; `frontend/src/core/auth/` holds only a README with the plan. Where the auth pages will live is not decided yet.

## Tables
None yet. Planned:
- `users`: email, password_hash (argon2), role, email_verified, is_active/deleted_at
- `email_otps`: user, purpose (verify/reset), code hash, expiry, attempts

## Endpoints
None yet. Planned under `/api/auth/...`: signup, login, refresh, logout, verify-email (OTP), password reset.

## Service functions other modules call
None yet. Planned: `@role_required(...)` decorators; `ca_has_active_access(ca_id, business_id)`; `get_current_user()`.

## Depends on
core-infra (password hashing in core/security, email in core/email), marketplace (engagement status for `ca_has_active_access`).

## Contracts (don't change without telling the team)
- JWT carries a `role` claim: `business` | `ca` | `admin`
- A CA reads business data ONLY through `ca_has_active_access(ca_id, business_id)` (rule 5)
- JWT errors must use the standard error body (configure flask-jwt-extended callbacks)

## Known issues
None yet.
