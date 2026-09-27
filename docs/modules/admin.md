# admin: admin shell, users and CAs, service catalog

## Purpose
The admin area shell, user/CA management (verify, suspend, soft-delete), the service catalog editor and the admin action audit log. Every admin screen, including other modules' config screens, is a page in `frontend/src/pages/admin/` registered in the admin area of `frontend/src/routes.jsx`.

## What exists now
CA verification, the user list and the home-page counts.
- **Backend:** `app/services/admin_service.py` (calls other modules' service functions; writes `admin_audit_log` itself): `get_dashboard`, `get_stats` (users by role, businesses, CAs by status, open engagements), `list_users(role, search, page, page_size)`, `list_cas(status)`, `get_ca`, `get_ca_certificate` (the file, admins only), `verify_ca` and `reject_ca` (reason required): each emails the CA (`ca_verified.txt`, `ca_rejected.txt`) and writes an audit row (`ca_profile.verify` / `ca_profile.reject`, the reason in `details`). Routes in `app/routes/admin.py`, schemas in `app/schemas/admin.py`.
- **Frontend:** `/admin` shows the counts ("CAs pending verification" links to the list). "Users & CAs" at `/admin/users` (`pages/admin/AdminUsersPage.jsx`): the "Pending verification" tab first (CAs waiting, longest first, certificate uploaded or missing, "Review ...") and "All users" (role filter, name/email search, pages). `/admin/cas/:caId` (`pages/admin/AdminCaDetailPage.jsx`): every profile field including the CoP number, "Open the certificate" (downloaded with `apiDownload()`), Verify (needs the certificate) and Reject with a reason. Hooks in `api/admin.js`.
- **Tests:** `tests/test_admin_ca_verification.py`, `tests/test_admin_dashboard.py`; `pages/admin/AdminUsersPage.test.jsx`.

## Tables
Created by migration `schema: complete data model` (no service, route or page uses them yet). Columns, constraints and status values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/admin.py`.
- `admin_audit_log`: admin, action, target type + id (no FK), details; append-only

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/v1/admin/dashboard` | admin | `{message}` (welcome text) |
| GET | `/api/v1/admin/stats` | admin | `{users_by_role: {business, ca, admin}, businesses, cas_by_status: {pending, verified, rejected}, open_engagements}` |
| GET | `/api/v1/admin/users?role=&search=&page=&page_size=` | admin | `{items: [{id, full_name, email, role, is_active, email_verified, created_at}], page, page_size, total}`, newest first |
| GET | `/api/v1/admin/cas?status=` | admin | CA profiles (all fields, the CoP number too), the longest-waiting first |
| GET | `/api/v1/admin/cas/<id>` | admin | one CA · 404 `CA_NOT_FOUND` |
| GET | `/api/v1/admin/cas/<id>/certificate` | admin | the file (its own MIME type) · 404 `CERTIFICATE_MISSING` |
| POST | `/api/v1/admin/cas/<id>/verify` | admin | the CA, `verified` · 409 `CERTIFICATE_MISSING` |
| POST | `/api/v1/admin/cas/<id>/reject` | admin | body `{reason}` (required) → the CA, `rejected` |

Planned: suspend or remove users, the catalog and rule editors, regulatory approvals.

## Service functions other modules call
None (admin only calls others).

## Depends on
core-auth (users), marketplace (CA verification, service catalog).

## Contracts (don't change without telling the team)
- No database-structure changes from the UI; admins edit configuration data only

## Known issues
None yet.
