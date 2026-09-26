# core-auth: authentication and access control

## Purpose
Users, signup/login for businesses and CAs, JWT access/refresh tokens with a role claim, email OTP, password reset, the seeded admin, and the shared access-control helpers (`app/utils/decorators.py`).

## What exists now
Basic login works: email + password → JWT access token, role-checked endpoints, demo users. No signup, OTP, password reset or refresh token yet.
- **Backend** (`backend/app/`):
  - `models/user.py`: `User` (`users` table).
  - `services/auth_service.py`: `authenticate()`, which always checks an argon2 hash, even for an unknown email, so timing doesn't reveal which emails exist. It rejects inactive or deleted users and rehashes outdated hashes. Also `issue_access_token()` (token contents), `get_active_user()` and `normalize_email()`.
  - `utils/jwt_handlers.py`: the JWT callbacks (load the user per request, token errors in the standard error body).
  - `routes/auth.py` + `schemas/auth.py`: login and me.
  - `seed.py`: `seed_demo_users()`, one demo user per role from `DEMO_*` in `.env`, idempotent; first in `SEEDS`.
- **Password hashing:** `backend/app/utils/passwords.py` (`hash_password`, `verify_password`, `needs_rehash`; argon2-cffi defaults).
- **Access control:** `backend/app/utils/decorators.py` has `roles_required(*roles)`, `login_required` (any role) and `current_user()`. The role is checked against the DB row, not only the token claim.
- **Enum:** `UserRole` (`business` | `ca` | `admin`) in `backend/app/models/enums.py`.
- **Config:** `JWT_ACCESS_TOKEN_EXPIRES` from `JWT_ACCESS_TOKEN_MINUTES` (default 60).
- **OpenAPI:** bearer auth is the global default (`API_SPEC_OPTIONS["security"]`). Public endpoints opt out with `@blp.doc(security=[])`.
- **Frontend** (`frontend/src/`):
  - `context/AuthProvider.jsx` (session in localStorage; TODO: move to a refresh cookie). It hands the token and `logout` to `apiFetch()` (`setAuth()` in `api/client.js`), which adds the Bearer header and logs out on any 401 to a request that carried a token.
  - `useAuth()` in `hooks/useAuth.js`; `login()` throws `ApiRequestError` (`api/client.js`) with the API error code.
  - `components/RequireRole.jsx` guard; `ROLE_HOME` and the localStorage session in `lib/session.js`.
  - The login page is `pages/LoginPage.jsx` (`/login`).
- **Tests:**
  - `backend/tests/test_auth_login.py`: success, email normalization, wrong password vs unknown email, dummy-hash check, inactive, soft-deleted, rehash, validation, rate limit.
  - `backend/tests/test_auth_me_and_permissions.py`: `/me` with no, bad, expired and deactivated tokens; role read from the DB; OpenAPI security.
  - `backend/tests/test_seed_command.py`: demo users, idempotent, skip when variables are missing.
  - `frontend/src/context/AuthProvider.test.jsx` and `frontend/src/pages/LoginPage.test.jsx`.
- **Test fixtures** (`backend/tests/conftest.py`): `make_user(role=..., **fields)` and `auth_headers(user)`. Rate-limit counters are reset before each test; the limiter stays on in `TestingConfig`.

## Tables
- `users` (implemented): `id`, `email` (unique, stored trimmed and lowercased), `password_hash` (argon2), `full_name`, `role` (`user_role` CHECK: `business`/`ca`/`admin`), `is_active`, `deleted_at`, `created_at`, `updated_at`. Migration `core-auth: create users table`.

Planned:
- `users.email_verified` (with the OTP task, in a new migration)
- `email_otps`: user, purpose (verify/reset), code hash, expiry, attempts

## Endpoints
| Method | Path | Who | Returns / errors |
|---|---|---|---|
| POST | `/api/v1/auth/login` | public, **10 per minute per IP** | `{access_token, user}` · 401 `INVALID_CREDENTIALS` (unknown email and wrong password alike) · 403 `ACCOUNT_INACTIVE` · 422 · 429 `TOO_MANY_REQUESTS` |
| GET | `/api/v1/auth/me` | any role | `{id, email, full_name, role}` |

Token errors on any protected endpoint: 401 `AUTH_REQUIRED` (no token), `TOKEN_INVALID`, `TOKEN_EXPIRED`, `ACCOUNT_INACTIVE` (user deactivated after the token was issued). Wrong role: 403 `FORBIDDEN`.

Planned: signup, refresh, logout, verify-email (OTP), password reset.

## Service functions other modules call
- `roles_required(*roles)`, `login_required` and `current_user()` from `app.utils.decorators`: one of the decorators on every protected endpoint (examples: `backend/app/routes/compliance.py`; `/auth/me` in `backend/app/routes/auth.py`).
- `UserRole` from `app.models.enums`.
- `issue_access_token(user)`, `get_active_user(user_id)`, `normalize_email(email)` from `app.services.auth_service`.
- Planned: `ca_has_active_access(ca_id, business_id)`.

## Depends on
core-infra (email, planned in `app/utils/email.py`), marketplace (engagement status for `ca_has_active_access`).

## Contracts (don't change without telling the team)
- JWT: `sub` = user id (UUID string), `role` claim = `business` | `ca` | `admin`, expiry from `JWT_ACCESS_TOKEN_MINUTES`
- Any 401 means "not logged in any more": the frontend clears the session and shows `/login`
- A CA reads business data ONLY through `ca_has_active_access(ca_id, business_id)` (rule 5)
- JWT errors use the standard error body (done in `app/utils/jwt_handlers.py`)
- Every endpoint needs a token unless it has `@blp.doc(security=[])` AND no role decorator

## Known issues
- Access token only, stored in localStorage (XSS-readable). Moving to an httpOnly refresh-token cookie is planned.
- No logout endpoint or token revocation: a stolen token works until it expires (a deactivated user is still rejected at once).
- The rate limit uses in-memory storage (per process): the counters reset when the API restarts.
