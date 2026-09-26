# admin: admin shell, users and CAs, service catalog

## Purpose
The admin area shell, user/CA management (verify, suspend, soft-delete), the service catalog editor and the admin action audit log. Every admin screen, including other modules' config screens, is a page in `frontend/src/pages/admin/` registered in the admin area of `frontend/src/routes.jsx`.

## What exists now
Only the admin dashboard stub; no admin features yet.
- Backend: `GET /api/v1/admin/dashboard` (admin role only) returns a welcome message: route in `app/routes/admin.py`, `AdminDashboardSchema` in `app/schemas/admin.py`, `get_dashboard(user)` in `app/services/admin_service.py`, tests in `tests/test_admin_dashboard.py`. No models or seed data. The demo admin user is seeded by `seed_demo_users()` (core-auth).
- Frontend: `pages/admin/AdminDashboardPage.jsx` is the admin area home (`/admin`, index route, nav "Dashboard"), using `useAdminDashboard()` from `api/admin.js`; placeholder "Users & CAs" page at `/admin/users` (`pages/admin/AdminUsersPage.jsx`). The sidebar layout (`AppShell`) is in frontend core.

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
