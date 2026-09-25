# admin: admin shell, users and CAs, service catalog

## Purpose
The admin area shell, user/CA management (verify, suspend, soft-delete), the service catalog editor and the admin action audit log. Other modules' admin screens are built by their owners and appear here through route aggregation.

## Owner
Member C (CA side & platform shell)

Folders: `backend/app/modules/admin/`, `frontend/src/features/admin/`

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [ ] ADM-01 · P1 · C · Admin shell + list users/CAs + verify-CA toggle
- [ ] ADM-02 · P2 · C · Suspend/remove (soft delete) users and CAs
- [ ] ADM-03 · P3 · C · Service catalog editor
- [ ] ADM-04 · P4 · C · Admin action audit log

## Tables owned
- `admin_audit_log` (planned, P4): admin, action, target, details, timestamp

## Endpoints exposed
Planned: `/api/admin/users/...`, `/api/admin/cas/...`.

## Service functions others may call
_None yet._

## Depends on
core-auth (users), marketplace (CA verification, service catalog).

## Contracts others rely on
- No database-structure changes from the UI; admins edit configuration data only

## Known issues
_None yet._

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0: created this doc and its task list.
