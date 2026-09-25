# compliance: obligations, calendar, item pages, dashboard

## Purpose
Turns a regulatory profile into dated compliance items for the 7 forms, shows them in the calendar and on the home dashboard, runs the item page (explanation, self-file path, consult-a-CA hand-off), the status lifecycle, checklists, instruction pages, peer insights and the admin editors for its config.

## Owner
Member A (Business domain)

Folders: `backend/app/modules/compliance/`, `frontend/src/features/compliance/`

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [ ] COM-01 · P1 · A · Obligation templates for all 7 forms (placeholder due-date rules, TODO_VERIFY) + compliance item generation
- [ ] COM-02 · P1 · A · Calendar (month + list views) with item statuses
- [ ] COM-03 · P1 · A · Item page: explanation placeholder + self-file path (mark filed + optional acknowledgement upload) + consult-a-CA hand-off (form code to marketplace)
- [ ] COM-04 · P1 · A · Basic home dashboard (next deadline, due/overdue counts)
- [ ] COM-05 · P2 · A · Verified due-date rules (monthly/QRMP/quarterly/yearly, audit-dependent ITR date)
- [ ] COM-06 · P2 · A · Checklists from content/ + checklist UI with tick state
- [ ] COM-07 · P2 · A · Instruction pages rendered from content/ in a polished layout
- [ ] COM-08 · P2 · A · Full status lifecycle incl. Overdue and "With CA" from engagements
- [ ] COM-09 · P3 · A · Peer insights (segmented, ≥10-user rule)
- [ ] COM-10 · P3 · A · Admin editors: rules/thresholds, obligation templates, checklists, instructions

## Tables owned
- `obligation_templates` (planned config): form code, applicability, frequency, due-date rule, `source_reference`, `effective_from/to`
- `compliance_items` (planned): business, form, period, FY, due date, status, path (self/CA), filed_at, acknowledgement document
- `checklist_ticks` (planned): per item, which checklist entries the user has

## Endpoints exposed
Planned: `/api/compliance/...` (calendar, items, dashboard); admin editors at `/api/admin/compliance/...`.

## Service functions others may call
- Planned: `list_items(business_id, ...)`, `get_item(item_id)`, `mark_filed(item_id, ...)`, `upcoming_items(days)` (used by alerts, ca_workspace, marketplace)

## Depends on
onboarding (regulatory profile), documents (acknowledgement upload), marketplace ("With CA" status from engagements).

## Contracts others rely on
- Status values: `Upcoming → Docs pending → Ready → With CA → Filed → Filed–verified`, plus `Overdue` from any pre-filed state
- Form codes: `ITR`, `GSTR-1`, `GSTR-3B`, `CMP-08`, `GSTR-4`, `24Q`, `26Q` (same as `content/forms/<code>/`)

## Known issues
_None yet._

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0: created this doc and its task list.
