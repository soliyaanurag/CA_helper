# admin: admin shell, users and CAs, service catalog

## Purpose
The admin area shell, user/CA management (verify, suspend, soft-delete), the service catalog editor and the admin action audit log. Every admin screen, including other modules' config screens, is a page in `frontend/src/pages/admin/` registered in the admin area of `frontend/src/routes.jsx`.

## What exists now
CA verification, the user list with suspend / reactivate (AD4), the home-page counts with the filing numbers (AD5)
and the audit log (AD8). Not yet: the catalog and rule editors, removing (soft-deleting) accounts.
- **Backend:** `app/services/admin_service.py` (calls other modules' service functions; writes `admin_audit_log`
  itself): `get_dashboard`, `get_stats` (users by role, businesses, CAs by status, open engagements, and from
  compliance: filings by status, filings due so far, late ones and the overdue rate), `list_users(role, search, page,
  page_size)`, `list_cas(status)`, `get_ca`, `get_ca_certificate` (the file, admins only), `verify_ca` and
  `reject_ca` (reason required): each emails the CA (`ca_verified.txt`, `ca_rejected.txt`) and writes an audit row
  (`ca_profile.verify` / `ca_profile.reject`, the reason in `details`). Routes in `app/routes/admin.py`, schemas in
  `app/schemas/admin.py`.
  - **Suspend (AD4):** `suspend_user(admin, user_id, reason)`: `users.is_active = false` (`auth_service.set_user_active`).
    The user cannot log in (403 `ACCOUNT_INACTIVE`, "This account is suspended. Contact the CA Helper team…") and a
    token they still hold stops working at once (401). A suspended CA leaves the marketplace (only live accounts
    are listed); their `requested` and `quoted` engagements are cancelled and each business gets a tray entry and an
    email (`marketplace_service.cancel_open_requests_of_ca`); **active engagements stay** (the business still sees
    its filings "With CA"; the admin decides what happens next). An admin cannot suspend themselves (409
    `CANNOT_SUSPEND_SELF`); twice → 409 `ALREADY_SUSPENDED`. `reactivate_user` → active again (409 `NOT_SUSPENDED`);
    cancelled requests stay cancelled. Both write an audit row (`user.suspend` with `{reason, cancelled_requests}`,
    `user.reactivate`).
  - **Audit log (AD8):** `list_audit_log(page, page_size)`: newest first, with the admin's name and, for a user or
    CA profile, the target's name.
- **Frontend:** `/admin` shows the counts ("CAs pending verification" links to the list) and an "Overdue rate" card
  with filings by status. "Users & CAs" at `/admin/users` (`pages/admin/AdminUsersPage.jsx`): the "Pending
  verification" tab first (CAs waiting, longest first, certificate uploaded or missing, "Review ...") and "All users"
  (role filter, name/email search, pages, "Account" Active / Suspended with Suspend (asks for an optional reason)
  or Reactivate; no button on your own row). `/admin/cas/:caId` (`pages/admin/AdminCaDetailPage.jsx`): every profile
  field including the CoP number, "Open the certificate" (downloaded with `apiDownload()`), Verify (needs the
  certificate) and Reject with a reason. `/admin/audit` (`pages/admin/AdminAuditLogPage.jsx`, nav "Audit log"):
  when, admin, action in words, who / what, details, pages. Hooks in `api/admin.js` (`suspendUser`,
  `reactivateUser`, `useAuditLog` added).
- **Tests:** `tests/test_admin_ca_verification.py`, `tests/test_admin_dashboard.py`, `tests/test_admin_users.py`
  (suspend: login refused and token stopped, reactivate, checks, a suspended CA's requests cancelled and listing
  gone, roles; audit log order, names, pages; filing numbers and overdue rate); `pages/admin/AdminUsersPage.test.jsx`
  (counts and overdue rate, suspend with a reason, reactivate, no button for yourself, the audit log page).

## Tables
Created by migration `schema: complete data model`. Columns, constraints and status values: `docs/DATA_MODEL.md`.
Model file: `backend/app/models/admin.py`.
- `admin_audit_log` **(used)**: admin, action, target type + id (no FK), details; append-only

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/v1/admin/dashboard` | admin | `{message}` (welcome text) |
| GET | `/api/v1/admin/stats` | admin | `{users_by_role: {business, ca, admin}, businesses, cas_by_status: {pending, verified, rejected}, open_engagements, filings_by_status: {status: n}, filings_due_so_far, filings_late, overdue_rate}` (`overdue_rate` in %, null before anything is due) |
| GET | `/api/v1/admin/users?role=&search=&page=&page_size=` | admin | `{items: [{id, full_name, email, role, is_active, email_verified, created_at}], page, page_size, total}`, newest first |
| POST | `/api/v1/admin/users/<id>/suspend` | admin | body `{reason?}` → the user, `is_active: false` · 404 `USER_NOT_FOUND` · 409 `CANNOT_SUSPEND_SELF`, `ALREADY_SUSPENDED` |
| POST | `/api/v1/admin/users/<id>/reactivate` | admin | the user, `is_active: true` · 404 `USER_NOT_FOUND` · 409 `NOT_SUSPENDED` |
| GET | `/api/v1/admin/audit-log?page=&page_size=` | admin | `{items: [{id, admin_name, action, target_type, target_id, target_name, details, created_at}], page, page_size, total}`, newest first |
| GET | `/api/v1/admin/cas?status=` | admin | CA profiles (all fields, the CoP number too), the longest-waiting first |
| GET | `/api/v1/admin/cas/<id>` | admin | one CA · 404 `CA_NOT_FOUND` |
| GET | `/api/v1/admin/cas/<id>/certificate` | admin | the file (its own MIME type) · 404 `CERTIFICATE_MISSING` |
| POST | `/api/v1/admin/cas/<id>/verify` | admin | the CA, `verified` · 409 `CERTIFICATE_MISSING` |
| POST | `/api/v1/admin/cas/<id>/reject` | admin | body `{reason}` (required) → the CA, `rejected` |

Planned: removing accounts, the catalog and rule editors, regulatory approvals.

## Service functions other modules call
None (admin only calls others).

## Depends on
core-auth (users: `get_user_for_admin`, `set_user_active`, `names_of`), marketplace (CA verification,
`cancel_open_requests_of_ca`, `ca_names`, service catalog), compliance (`filing_stats`), documents (certificate).

## Contracts (don't change without telling the team)
- No database-structure changes from the UI; admins edit configuration data only
- Every admin action writes one `admin_audit_log` row (no PII beyond the reason the admin types, never document
  contents)

## Known issues
- A suspended CA's **active** engagements are left as they are; nothing reassigns the business's filings yet.
- A suspended business's open requests to CAs are not cancelled (the CA can still answer them).
- The suspension reason is not emailed to the user.
