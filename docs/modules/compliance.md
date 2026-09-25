# compliance: obligations, calendar, item pages, dashboard

## Purpose
Turns a regulatory profile into dated compliance items for the 7 forms, shows them in the calendar and on the home dashboard, runs the item page (explanation, self-file path, consult-a-CA hand-off), the status lifecycle, checklists, instruction pages, peer insights and the admin editors for its config.

## What exists now
Skeleton only; no features yet.
- Backend (`backend/app/modules/compliance/`): the `compliance` blueprint is registered under `/api` with no routes; `models.py`, `schemas.py` and `services.py` are empty; `seed()` does nothing; `tests/` is empty.
- Frontend (`frontend/src/features/compliance/`): one placeholder page, "Compliance calendar" at `/app/compliance` (business nav), built from `ModulePlaceholder`; `api.ts` is empty.
- Form content: `content/forms/<FORM>/` holds a TODO template (explanation, instructions, checklist) for each of the 7 forms; nothing reads it yet.

## Tables
None yet. Planned:
- `obligation_templates` (config): form code, applicability, frequency, due-date rule, `source_reference`, `effective_from/to`
- `compliance_items`: business, form, period, FY, due date, status, path (self/CA), filed_at, acknowledgement document
- `checklist_ticks`: per item, which checklist entries the user has

## Endpoints
None yet. Planned: `/api/compliance/...` (calendar, items, dashboard); admin editors at `/api/admin/compliance/...`.

## Service functions other modules call
None yet. Planned: `list_items(business_id, ...)`, `get_item(item_id)`, `mark_filed(item_id, ...)`, `upcoming_items(days)` (used by alerts, ca_workspace, marketplace).

## Depends on
onboarding (regulatory profile), documents (acknowledgement upload), marketplace ("With CA" status from engagements).

## Contracts (don't change without telling the team)
- Status values: `Upcoming → Docs pending → Ready → With CA → Filed → Filed–verified`, plus `Overdue` from any pre-filed state (authoritative list: `docs/DATA_MODEL.md`, "Status values")
- Form codes: `ITR`, `GSTR-1`, `GSTR-3B`, `CMP-08`, `GSTR-4`, `24Q`, `26Q` (same as `content/forms/<code>/`)

## Known issues
None yet.
