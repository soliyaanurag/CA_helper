# core/auth (frontend)

Owner: Member C. Empty in Phase 0.

Planned (FE-02, Phase 1):

- `AuthProvider` / `useAuth()`: current user, role (`business` | `ca` | `admin`), login/logout, token refresh
- route guards used by the business, CA and admin layouts
- an openapi-fetch middleware (`api.use(...)`) that adds `Authorization: Bearer <access token>`
