# ca_workspace: CA multi-client dashboard and client workspace

## Purpose
The CA's multi-client dashboard with urgency scores, the deadline batch view, and the client workspace (profile, calendar, vault, document requests, mark filed, private notes).

## What exists now
Skeleton only; no features yet.
- Backend (`backend/app/modules/ca_workspace/`): the `ca_workspace` blueprint is registered under `/api` with no routes; `models.py`, `schemas.py` and `services.py` are empty; `seed()` does nothing; `tests/` is empty.
- Frontend (`frontend/src/features/ca_workspace/`): one placeholder page, "My clients" at `/ca/clients` (CA nav), built from `ModulePlaceholder`; `api.ts` is empty.

## Tables
None yet. Planned:
- `document_requests`: engagement/item, requested doc type, message, status (shown as client to-dos)
- `ca_notes`: private notes per client

## Endpoints
None yet. Planned: `/api/v1/ca-workspace/...`.

## Service functions other modules call
None yet.

## Depends on
core-auth (`ca_has_active_access`), marketplace (engagements), compliance (items), documents (vault), regulatory (urgency input).

## Contracts (don't change without telling the team)
- Every read of client data goes through `ca_has_active_access` (rule 5)

## Known issues
None yet.
