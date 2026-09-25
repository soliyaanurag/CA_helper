# core/auth (frontend)

Empty so far.

Planned:

- `AuthProvider` / `useAuth()`: current user, role (`business` | `ca` | `admin`), login/logout, token refresh
- route guards used by the business, CA and admin layouts
- an openapi-fetch middleware (`api.use(...)`) that adds `Authorization: Bearer <access token>`
