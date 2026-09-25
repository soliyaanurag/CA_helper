# admin: admin shell, users and CAs, service catalog

## Purpose
The admin area shell, user/CA management (verify, suspend, soft-delete), the service catalog editor and the admin action audit log. Other modules' admin screens live in their own `features/<module>/admin/` folders and appear here through route aggregation.

## What exists now
Only the admin dashboard stub; no admin features yet.
- Backend (`backend/app/modules/admin/`): `GET /api/v1/admin/dashboard` (admin role only) returns a welcome message: route in `routes.py`, `AdminDashboardSchema` in `schemas.py`, `get_dashboard(user)` in `services.py`, tests in `tests/test_dashboard.py`. No models; `seed()` does nothing. The demo admin user is seeded by core-auth.
- Frontend (`frontend/src/features/admin/`): `AdminDashboardPage` is the admin area home (`/admin`, index route, nav "Dashboard"), using `useAdminDashboard()` from `api.ts`; placeholder "Users & CAs" page at `/admin/users`. The admin layout itself (`AdminLayout`) is in frontend core.

## Tables
None yet. Planned:
- `admin_audit_log`: admin, action, target, details, timestamp

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/v1/admin/dashboard` | admin | `{message}` (welcome text; grows into the admin home) |

Planned: `/api/v1/admin/users/...`, `/api/v1/admin/cas/...`.

## Service functions other modules call
None yet.

## Depends on
core-auth (users), marketplace (CA verification, service catalog).

## Contracts (don't change without telling the team)
- No database-structure changes from the UI; admins edit configuration data only

## Known issues
None yet.
