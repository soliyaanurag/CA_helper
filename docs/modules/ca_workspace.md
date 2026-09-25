# ca_workspace: CA multi-client dashboard and client workspace

## Purpose
The CA's multi-client dashboard with urgency scores, the deadline batch view, and the client workspace (profile, calendar, vault, document requests, mark filed, private notes).

## What exists now
Only the CA dashboard stub; no workspace features yet.
- Backend (`backend/app/modules/ca_workspace/`): `GET /api/v1/ca-workspace/dashboard` (CA role only) returns a welcome message: route in `routes.py`, `CaDashboardSchema` in `schemas.py`, `get_dashboard(user)` in `services.py`, tests in `tests/test_dashboard.py`. No models; `seed()` does nothing.
- Frontend (`frontend/src/features/ca_workspace/`): `CaDashboardPage` is the CA area home (`/ca`, index route, nav "Dashboard"), using `useCaDashboard()` from `api.ts`; placeholder "My clients" page at `/ca/clients`.

## Tables
None yet. Planned:
- `document_requests`: engagement/item, requested doc type, message, status (shown as client to-dos)
- `ca_notes`: private notes per client

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/v1/ca-workspace/dashboard` | ca | `{message}` (welcome text; grows into the multi-client dashboard) |

Planned: more of `/api/v1/ca-workspace/...`.

## Service functions other modules call
None yet.

## Depends on
core-auth (`ca_has_active_access`), marketplace (engagements), compliance (items), documents (vault), regulatory (urgency input).

## Contracts (don't change without telling the team)
- Every read of client data goes through `ca_has_active_access` (rule 5)

## Known issues
None yet.
