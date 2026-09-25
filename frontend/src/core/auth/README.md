# core/auth (frontend)

Login state and route guards. Backend side: `backend/app/core/auth/` and `docs/modules/core-auth.md`.

- `session.ts`: `User` / `Role` types (from the generated API types), `ROLE_HOME` (where each role lands),
  and the session in localStorage. TODO: move the token to a refresh-token cookie.
- `auth-context.ts`: `useAuth()` → `{ user, login, logout }`. `login` throws `ApiRequestError`
  (`core/api/errors.ts`) whose `code` is e.g. `INVALID_CREDENTIALS`.
- `AuthProvider.tsx`: holds the session; an `api.use(...)` middleware adds `Authorization: Bearer <token>` to
  every request and logs out on any 401 to a request that carried a token.
- `RequireRole.tsx`: guard around each area layout (`core/routes.tsx`). Not logged in → `/login`; wrong role →
  your own home.

The login page is `core/pages/LoginPage.tsx`. Tests: `auth.test.tsx` here and `core/pages/LoginPage.test.tsx`,
using the helpers in `src/test/utils.tsx`.

Planned: signup, refresh token (httpOnly cookie), email OTP.
