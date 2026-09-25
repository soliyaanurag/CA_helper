# ca_workspace: CA multi-client dashboard and client workspace

## Purpose
The CA's multi-client dashboard with urgency scores, the deadline batch view, and the client workspace (profile, calendar, vault, document requests, mark filed, private notes).

## Owner
Member C (CA side & platform shell)

Folders: `backend/app/modules/ca_workspace/`, `frontend/src/features/ca_workspace/`

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [ ] CAW-01 · P1 · C · Client list dashboard (active engagements, next deadline, overdue count)
- [ ] CAW-02 · P1 · C · Client calendar view + mark item filed with acknowledgement upload
- [ ] CAW-03 · P2 · C · Client workspace: profile, vault, document requests (to-dos on client side)
- [ ] CAW-04 · P3 · C · Urgency score with "why flagged" breakdown
- [ ] CAW-05 · P3 · C · Deadline batch view
- [ ] CAW-06 · P4 · C · Bulk document requests
- [ ] CAW-07 · P4 · C · Private CA notes

## Tables owned
- `document_requests` (planned): engagement/item, requested doc type, message, status (shown as client to-dos)
- `ca_notes` (planned, P4): private notes per client

## Endpoints exposed
Planned: `/api/ca-workspace/...`.

## Service functions others may call
_None yet._

## Depends on
core-auth (`ca_has_active_access`), marketplace (engagements), compliance (items), documents (vault), regulatory (urgency input).

## Contracts others rely on
- Every read of client data goes through `ca_has_active_access` (rule 5)

## Known issues
_None yet._

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0: created this doc and its task list.
