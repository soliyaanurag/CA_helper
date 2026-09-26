# core-auth: authentication and access control

## Purpose
Users, signup/login for businesses and CAs, JWT access/refresh tokens with a role claim, email OTP, password reset, the seeded admin, and the shared access-control helpers (`app/utils/decorators.py`).

## What exists now
Signup with email OTP verification, login (refused until the email is verified), forgot/reset password, change password, JWT access token, role-checked endpoints, demo users. No refresh token or logout endpoint yet.
- **Backend** (`backend/app/`):
  - `models/user.py`: `User` (`users` table). `models/email_otp.py`: `EmailOtp` (`email_otps`) and `OtpPurpose`.
  - `services/auth_service.py`:
    - `signup()` creates a business or CA account with `email_verified_at` empty and emails a verification code.
    - `verify_email()` and `resend_verification_code()` handle that code.
    - `authenticate()` always checks an argon2 hash, even for an unknown email, so timing doesn't reveal which emails exist. It rejects inactive or deleted users, then unverified emails, and rehashes outdated hashes.
    - `request_password_reset()` and `reset_password()` handle the reset code; a successful reset also verifies the email.
    - `change_password()` needs the current password.
    - Also `issue_access_token()` (token contents), `get_active_user()` and `normalize_email()`.
  - `utils/jwt_handlers.py`: the JWT callbacks (load the user per request, token errors in the standard error body).
  - `routes/auth.py` + `schemas/auth.py`: every endpoint below. The password rule is `validate_new_password()` in `schemas/auth.py`.
  - `templates/email/`: `verify_email.txt`, `reset_password.txt`, `password_changed.txt` (sent with `send_email()`, see core-infra).
  - `seed.py`: `seed_demo_users()`, one verified demo user per role from `DEMO_*` in `.env`, idempotent; first in `SEEDS`.
- **One-time codes:** 6 random digits (`secrets`), stored only as an argon2 hash. Valid for 10 minutes (`OTP_LIFETIME`) and 5 wrong guesses (`OTP_MAX_ATTEMPTS`). Only the newest code per user and purpose counts, so a new code cancels the old one. At most one new code per minute per account and purpose (`OTP_RESEND_WAIT`); extra requests are ignored silently. A code's purpose (`verify_email` or `reset_password`) must match the endpoint.
- **Password rule:** 8 to 128 characters with at least one letter and one number, for every new password (signup, reset, change). The frontend checks the same rule in `frontend/src/lib/authRules.js`.
- **Password hashing:** `backend/app/utils/passwords.py` (`hash_password`, `verify_password`, `needs_rehash`; argon2-cffi defaults).
- **Access control:** `backend/app/utils/decorators.py` has `roles_required(*roles)`, `login_required` (any role) and `current_user()`. The role is checked against the DB row, not only the token claim.
- **Enums:** `UserRole` (`business` | `ca` | `admin`) in `backend/app/models/enums.py`; `OtpPurpose` in `models/email_otp.py`.
- **Config:** `JWT_ACCESS_TOKEN_EXPIRES` from `JWT_ACCESS_TOKEN_MINUTES` (default 60).
- **OpenAPI:** bearer auth is the global default (`API_SPEC_OPTIONS["security"]`). Public endpoints opt out with `@blp.doc(security=[])`.
- **Frontend** (`frontend/src/`):
  - `context/AuthProvider.jsx` (session in localStorage; TODO: move to a refresh cookie). It hands the token and `logout` to `apiFetch()` (`setAuth()` in `api/client.js`), which adds the Bearer header and logs out on any 401 to a request that carried a token.
  - `useAuth()` in `hooks/useAuth.js`; `login()` throws `ApiRequestError` (`api/client.js`) with the API error code.
  - `api/auth.js`: `signup()`, `verifyEmail()`, `resendVerificationCode()`, `forgotPassword()`, `resetPassword()`, `changePassword()` (plain async functions around `apiFetch()`).
  - Public pages: `pages/LoginPage.jsx` (`/login`; links to signup and forgot password; on `EMAIL_NOT_VERIFIED` links to `/verify-email`; shows a `notice` passed in the location state), `SignupPage.jsx` (`/signup`), `VerifyEmailPage.jsx` (`/verify-email`), `ForgotPasswordPage.jsx` (`/forgot-password`), `ResetPasswordPage.jsx` (`/reset-password`). The email moves between them in the location state, never in the URL.
  - `pages/ChangePasswordPage.jsx` at `<area>/change-password` in every role's area (added by `roleArea()` in `routes.jsx`), linked from the sidebar by `AppShell`.
  - `components/RequireRole.jsx` guard; `ROLE_HOME` and the localStorage session in `lib/session.js`.
- **Tests:**
  - `backend/tests/test_auth_login.py`: success, email normalization, wrong password vs unknown email, dummy-hash check, inactive, soft-deleted, unverified, rehash, validation, rate limit.
  - `backend/tests/test_auth_signup.py`: unverified account, emailed code stored as a hash, CA signup, no admin signup, duplicate email, password rule, validation, login refused until verified, rate limit.
  - `backend/tests/test_auth_verify_email.py`: verify then log in, wrong code counted, too many guesses, expiry, unknown email, already verified, code format, resend replaces the old code, one code a minute, no account enumeration, rate limit.
  - `backend/tests/test_auth_password_reset.py`: full reset, no account enumeration, one code a minute, wrong code, single use, password rule, a verification code cannot reset, reset verifies the email, rate limit.
  - `backend/tests/test_auth_change_password.py`: every role, needs a login, wrong current password is 400, same password, password rule, rate limit.
  - `backend/tests/test_auth_me_and_permissions.py`: `/me` with no, bad, expired and deactivated tokens; role read from the DB; OpenAPI security (public auth endpoints vs protected ones).
  - `backend/tests/test_seed_command.py`: demo users (verified), idempotent, skip when variables are missing.
  - Frontend: `context/AuthProvider.test.jsx`, `pages/LoginPage.test.jsx`, `SignupPage.test.jsx`, `VerifyEmailPage.test.jsx`, `ResetPasswordPage.test.jsx` (forgot + reset), `ChangePasswordPage.test.jsx`.
- **Test fixtures** (`backend/tests/conftest.py`): `make_user(role=..., **fields)` (verified unless `email_verified_at=None`), `auth_headers(user)`, `mailbox` (emails "sent" during the test) and the helper `emailed_code(message)`. Rate-limit counters are reset before each test; the limiter stays on in `TestingConfig`.

## Tables
- `users` (implemented): `id`, `email` (unique, stored trimmed and lowercased), `password_hash` (argon2), `full_name`, `role` (`user_role` CHECK: `business`/`ca`/`admin`), `email_verified_at` (null until verified), `is_active`, `deleted_at`, `created_at`, `updated_at`. Migrations `core-auth: create users table` and `core-auth: email verification and one-time codes` (the second marks existing users verified).
- `email_otps` (implemented): `id`, `user_id` (FK `users`, indexed), `purpose` (`otp_purpose` CHECK: `verify_email`/`reset_password`), `code_hash` (argon2), `expires_at`, `attempts` (wrong guesses), `used_at`, `created_at`, `updated_at`. Rows are never deleted.

## Endpoints
| Method | Path | Who | Returns / errors |
|---|---|---|---|
| POST | `/api/v1/auth/signup` | public, **5 per minute per IP** | 201 `{id, email, full_name, role}`; `role` is `business` or `ca` · 409 `EMAIL_TAKEN` · 422 (password rule, name, email, role) · 429 |
| POST | `/api/v1/auth/verify-email` | public, **10 per minute per IP** | 204 · 400 `OTP_INVALID` (wrong, used or unknown) / `OTP_EXPIRED` (too old or too many guesses) · 409 `EMAIL_ALREADY_VERIFIED` · 422 · 429 |
| POST | `/api/v1/auth/verify-email/resend` | public, **3 per minute per IP** | always 204 (never reveals whether the email exists) · 429 |
| POST | `/api/v1/auth/login` | public, **10 per minute per IP** | `{access_token, user}` · 401 `INVALID_CREDENTIALS` (unknown email and wrong password alike) · 403 `ACCOUNT_INACTIVE`, `EMAIL_NOT_VERIFIED` · 422 · 429 `TOO_MANY_REQUESTS` |
| POST | `/api/v1/auth/forgot-password` | public, **3 per minute per IP** | always 204 · 429 |
| POST | `/api/v1/auth/reset-password` | public, **10 per minute per IP** | 204 · 400 `OTP_INVALID` / `OTP_EXPIRED` · 422 · 429 |
| POST | `/api/v1/auth/change-password` | any role, **10 per minute per IP** | 204 · 400 `WRONG_PASSWORD` (400, not 401, so the user stays logged in), `SAME_PASSWORD` · 422 · 429 |
| GET | `/api/v1/auth/me` | any role | `{id, email, full_name, role}` |

Request bodies: signup `{full_name, email, password, role}`; verify `{email, code}`; resend and forgot `{email}`; reset `{email, code, new_password}`; change `{current_password, new_password}`.

Token errors on any protected endpoint: 401 `AUTH_REQUIRED` (no token), `TOKEN_INVALID`, `TOKEN_EXPIRED`, `ACCOUNT_INACTIVE` (user deactivated after the token was issued). Wrong role: 403 `FORBIDDEN`.

Planned: refresh, logout.

## Service functions other modules call
- `roles_required(*roles)`, `login_required` and `current_user()` from `app.utils.decorators`: one of the decorators on every protected endpoint (examples: `backend/app/routes/compliance.py`; `/auth/me` in `backend/app/routes/auth.py`).
- `UserRole` from `app.models.enums`.
- `issue_access_token(user)`, `get_active_user(user_id)`, `normalize_email(email)` from `app.services.auth_service`.
- Planned: `ca_has_active_access(ca_id, business_id)`.

## Depends on
core-infra (`send_email()` in `app/utils/email.py`), marketplace (engagement status for `ca_has_active_access`).

## Contracts (don't change without telling the team)
- JWT: `sub` = user id (UUID string), `role` claim = `business` | `ca` | `admin`, expiry from `JWT_ACCESS_TOKEN_MINUTES`
- Any 401 means "not logged in any more": the frontend clears the session and shows `/login`. So a wrong current password on change-password is 400 `WRONG_PASSWORD`, never 401
- Signup creates only `business` and `ca` accounts; a new account cannot log in until its email is verified (403 `EMAIL_NOT_VERIFIED`)
- The password rule is the same in `backend/app/schemas/auth.py` and `frontend/src/lib/authRules.js`
- A CA reads business data ONLY through `ca_has_active_access(ca_id, business_id)` (rule 5)
- JWT errors use the standard error body (done in `app/utils/jwt_handlers.py`)
- Every endpoint needs a token unless it has `@blp.doc(security=[])` AND no role decorator

## Known issues
- Access token only, stored in localStorage (XSS-readable). Moving to an httpOnly refresh-token cookie is planned.
- No logout endpoint or token revocation: a stolen token works until it expires, even after a password change or reset (a deactivated user is still rejected at once).
- Signup answers 409 `EMAIL_TAKEN`, which reveals that an email has an account. Resend and forgot-password never reveal it, but their response time can (an email is sent only for a real account).
- Emails are sent inside the request. A slow or failing SMTP server slows the request; a failure is logged and the user can ask for a new code.
- Someone can sign up with an address they do not own. The account stays unverified, and the real owner can take it over with "Forgot password?" (the reset verifies the email).
- The rate limit uses in-memory storage (per process): the counters reset when the API restarts.
