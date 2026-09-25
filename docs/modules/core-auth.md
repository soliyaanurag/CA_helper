# core-auth: authentication and access control

## Purpose
Users, signup/login for businesses and CAs, JWT access/refresh tokens with a role claim, email OTP, password reset, the seeded admin, and the shared access-control helpers (`core/permissions.py`).

## Owner
Member A (Business domain)

Folders: `backend/app/core/auth/`, `backend/app/core/permissions.py`, auth pages in `frontend/src/features/` (decided in AUTH-01)

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [ ] AUTH-01 · P1 · A · Signup/login (business, CA), JWT access/refresh, role claim, auth pages
- [ ] AUTH-02 · P1 · A · Email OTP verification
- [ ] AUTH-03 · P1 · A · Role decorators + ca_has_active_access helper
- [ ] AUTH-04 · P1 · A · Seeded admin account
- [ ] AUTH-05 · P2 · A · Password reset via email OTP + rate limiting on login/OTP

## Tables owned
- `users` (planned): email, password_hash (argon2), role, email_verified, is_active/deleted_at
- `email_otps` (planned): user, purpose (verify/reset), code hash, expiry, attempts

## Endpoints exposed
Planned under `/api/auth/...`: signup, login, refresh, logout, verify-email (OTP), password reset.

## Service functions others may call
- Planned: `@role_required(...)` decorators; `ca_has_active_access(ca_id, business_id)`; `get_current_user()`

## Depends on
core-infra (password hashing in core/security, email in core/email), marketplace (engagement status for `ca_has_active_access`).

## Contracts others rely on
- JWT carries a `role` claim: `business` | `ca` | `admin`
- A CA reads business data ONLY through `ca_has_active_access(ca_id, business_id)` (rule 5)
- JWT errors must use the standard error body (configure flask-jwt-extended callbacks)

## Known issues
_None yet._

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0: created this doc and its task list.
