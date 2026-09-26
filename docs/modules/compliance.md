# compliance: obligations, calendar, item pages, dashboard

## Purpose
Turns a regulatory profile into dated compliance items for the 7 forms, shows them in the calendar and on the home dashboard, runs the item page (explanation, self-file path, consult-a-CA hand-off), the status lifecycle, checklists, instruction pages, peer insights and the admin editors for its config.

## What exists now
Only the business dashboard stub; no compliance features yet.
- Backend: `GET /api/v1/compliance/dashboard` (business role only) returns a welcome message: route in `app/routes/compliance.py`, `ComplianceDashboardSchema` in `app/schemas/compliance.py`, `get_dashboard(user)` in `app/services/compliance_service.py`, tests in `tests/test_compliance_dashboard.py` (success, other roles 403, no token 401). No models or seed data.
- Frontend: `pages/business/BusinessDashboardPage.jsx` is the business area home (`/business`, index route, nav "Dashboard"), using `useComplianceDashboard()` from `api/compliance.js`; placeholder "Compliance calendar" page at `/business/compliance` (`pages/business/CompliancePage.jsx`).
- Form content: `content/forms/<FORM>/` holds a TODO template (explanation, instructions, checklist) for each of the 7 forms; nothing reads it yet.

## Tables
None yet. Planned:
- `obligation_templates` (config): form code, applicability, frequency, due-date rule, `source_reference`, `effective_from/to`
- `compliance_items`: business, form, period, FY, due date, status, path (self/CA), filed_at, acknowledgement document
- `checklist_ticks`: per item, which checklist entries the user has

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/v1/compliance/dashboard` | business | `{message}` (welcome text; grows into the home dashboard) |

Planned: `/api/v1/compliance/...` (calendar, items); admin editors at `/api/v1/admin/compliance/...`.

## Service functions other modules call
None yet. Planned: `list_items(business_id, ...)`, `get_item(item_id)`, `mark_filed(item_id, ...)`, `upcoming_items(days)` (used by alerts, ca_workspace, marketplace).

## Depends on
onboarding (regulatory profile), documents (acknowledgement upload), marketplace (`with_ca` status from engagements).

## Contracts (don't change without telling the team)
- Status codes: `upcoming → docs_pending → ready → with_ca → filed → filed_verified`, plus `overdue` from any pre-filed state (codes and labels: `docs/DATA_MODEL.md`, "Status values")
- `GET /api/v1/compliance/dashboard` is the business home page's data (frontend `/business`)
- Form codes: `ITR`, `GSTR-1`, `GSTR-3B`, `CMP-08`, `GSTR-4`, `24Q`, `26Q` (same as `content/forms/<code>/`)

## Known issues
None yet.
