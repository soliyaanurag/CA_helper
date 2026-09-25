# admin: admin shell, users and CAs, service catalog

## Purpose
The admin area shell, user/CA management (verify, suspend, soft-delete), the service catalog editor and the admin action audit log. Other modules' admin screens live in their own `features/<module>/admin/` folders and appear here through route aggregation.

## What exists now
Skeleton only; no features yet.
- Backend (`backend/app/modules/admin/`): the `admin` blueprint is registered under `/api` with no routes; `models.py`, `schemas.py` and `services.py` are empty; `seed()` does nothing; `tests/` is empty.
- Frontend (`frontend/src/features/admin/`): one placeholder page, "Users & CAs" at `/admin/users` (admin nav), built from `ModulePlaceholder`; `api.ts` is empty. The admin layout itself (`AdminLayout`) is in frontend core.

## Tables
None yet. Planned:
- `admin_audit_log`: admin, action, target, details, timestamp

## Endpoints
None yet. Planned: `/api/v1/admin/users/...`, `/api/v1/admin/cas/...`.

## Service functions other modules call
None yet.

## Depends on
core-auth (users), marketplace (CA verification, service catalog).

## Contracts (don't change without telling the team)
- No database-structure changes from the UI; admins edit configuration data only

## Known issues
None yet.
