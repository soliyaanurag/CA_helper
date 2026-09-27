# compliance: obligations, calendar, item pages, dashboard

## Purpose
Turns a regulatory profile into dated compliance items for the 7 forms, shows them in the calendar and on the home dashboard, runs the item page (explanation, self-file path, consult-a-CA hand-off), the status lifecycle, checklists, instruction pages, peer insights and the admin editors for its config.

## What exists now
Obligation templates, the due-date calculator and filing creation work (CO1, CO2, CO3), plus a plain filings list (part of CO4) and the dashboard stub.
- **Backend:**
  - `services/compliance_service.py`: `financial_year_start()`, `fy_label()`, `periods_of_year()` (12 months, 4 quarters or the year), `due_date()` (reads the template's `due_date_rule`), `sync_filings(business_id, profile, today, keep_ids)` (makes this year's filings match the profile; used after registering and after every edit; does not commit), `create_filings(business_id, profile, today)` (the same for a new business, returns how many were added), `list_filings(business)`, `get_dashboard(user)` (welcome text).
  - `routes/compliance.py`: `GET /api/v1/compliance/dashboard`, `GET /api/v1/compliance/items`.
  - `schemas/compliance.py`: `ComplianceDashboardSchema`, `ComplianceItemSchema`.
  - `seed.py`: `seed_obligation_templates()` adds 9 templates for the 7 forms (GSTR-1 and GSTR-3B each have a monthly and a QRMP template), **all `TODO_VERIFY`**.
- **How filings are made (`sync_filings`):** for each template in force whose `applicability` matches the profile, one filing per period of the **current financial year, from 1 April**; a period whose due date has passed starts as `overdue` (the business may have filed it before joining; marking it filed comes with CO5), the rest `upcoming`. On a profile change: a filing that no longer applies is soft-deleted unless it is filed, `with_ca` or in an open engagement; one that applies again is reactivated (never inserted twice); a not-started filing whose period or due date changed gets the new one (switching monthly ↔ quarterly turns "Q1 2026-27" into "Apr 2026", which starts the same day). Running it again changes nothing.
- **Due-date rules** (JSON in `obligation_templates.due_date_rule`): monthly `{"day": 11}` = the 11th of the next month; quarterly `{"quarters": [[7, 13], [10, 13], [1, 13], [4, 13]]}` = [month, day] for Q1–Q4; yearly `{"month": 7, "day": 31}` after the financial year, with `audit_month`/`audit_day` for businesses with either audit (tax audit or accounts audited under another law) (ITR).
- **Tests:** `tests/test_compliance_due_dates.py` (periods and due dates), `tests/test_compliance_items.py` (which forms for QRMP, monthly and composition businesses; every period from 1 April, past ones overdue; idempotent; removed, reactivated, kept (filed, with a CA, open request) and moved filings; list sorted; 404 before registration), `tests/test_compliance_dashboard.py`.
- **Frontend:** `pages/business/BusinessDashboardPage.jsx`: the welcome text, four cards (next deadline with days left, due this month, overdue, with a CA) and a to-do list (quotes to answer, requests waiting, overdue filings, filings due within 30 days with no way of filing chosen), all computed from `useFilings()` and `useMyEngagements()`. "Compliance calendar" at `/business/compliance` (`pages/business/CompliancePage.jsx`): filter chips (All / GST / TDS / ITR and All / Upcoming / Overdue), then "Earlier this year: due dates already passed" (with "If you already filed this, you'll be able to mark it as filed.") and one table per month (form, period, due date, days left, coloured status badge from `components/StatusBadge.jsx`). Before registration both link to the Business profile page. Tests: `CompliancePage.test.jsx`, `BusinessDashboardPage.test.jsx`. A month grid comes later.
- Form content: `content/forms/<FORM>/` holds a TODO template (explanation, instructions, checklist) for each of the 7 forms; nothing reads it yet.

## Tables
Created by migration `schema: complete data model`. Columns, constraints and status values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/compliance.py`.
- `obligation_templates` (config): form code, frequency, applicability and due-date rule (JSONB), `source_reference`, `effective_from/to`. Seeded (9 rows).
- `compliance_items`: one filing per business, form and period (partial unique index on live rows), status, filing path, nil return, acknowledgement number and document
- `checklist_ticks`: ticked checklist keys (from `content/forms/<FORM>/checklist.yaml`); unticking deletes the row. Not used yet.

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/v1/compliance/dashboard` | business | `{message}` (welcome text; grows into the home dashboard) |
| GET | `/api/v1/compliance/items` | business | the business's filings, soonest due first: `id, form_code, fy, period_label, period_start, period_end, due_date, status, filing_path` · 404 `BUSINESS_NOT_FOUND` |

Planned: date-range and status filters on `/items` (CO4), `/items/{id}` (CO5), actions like `/items/{id}/mark-filed`; admin editors at `/api/v1/admin/compliance/...`.

## Service functions other modules call
- `sync_filings(business_id, profile, today, keep_ids=()) -> dict`: make this year's filings match the profile (see above; does not commit). Used by onboarding after an edit; `keep_ids` are filings in an open engagement.
- `create_filings(business_id, profile, today) -> int`: `sync_filings` for a new business, returns how many were added (does not commit). Used by onboarding after registering.
- `list_filings(business) -> list[ComplianceItem]`.
- `get_filings_by_ids(filing_ids, lock=False) -> {id: ComplianceItem}`: live filings by id; `lock=True` is
  `SELECT ... FOR UPDATE` until the caller commits (does not commit). Used by marketplace (engagements).
- `mark_filings_with_ca(filing_ids)`: status `with_ca`, filing path `ca` (does not commit). Called by marketplace
  when an engagement becomes `active` (the CA accepts, or the business accepts a quote).
- `due_date(template, period_end, quarter, audit) -> date`, `financial_year_start(day)`, `periods_of_year(frequency, fy_start)`.

## Depends on
onboarding (the regulatory profile, passed in by `register_business()`), core-auth (`current_business()`), documents (acknowledgement upload, later), marketplace (`with_ca` status from engagements, later).

## Contracts (don't change without telling the team)
- Status codes: `upcoming → docs_pending → ready → with_ca → filed → filed_verified`, plus `overdue` from any pre-filed state (codes and labels: `docs/DATA_MODEL.md`, "Status values")
- `GET /api/v1/compliance/dashboard` is the business home page's data (frontend `/business`)
- Form codes: `itr`, `gstr_1`, `gstr_3b`, `cmp_08`, `gstr_4`, `tds_24q`, `tds_26q` (`FormCode`; folders in `content/forms/` use the display names)
- Template `applicability` keys are `regulatory_profiles` column names; `{}` means every business
- Period labels: `"Apr 2026"` (monthly), `"Q1 2026-27"` (quarterly), `"FY 2026-27"` (yearly)

## Known issues
- **Every due-date rule is `TODO_VERIFY`** (`docs/TODO_VERIFY.md`); GSTR-3B QRMP uses the 22nd for every state (some states have the 24th).
- Only the current financial year is created; nothing creates next year's filings yet (a worker job, X2/ON14).
- The yearly ITR filing is the current year's (FY 2026-27, due in 2027); last year's return is not added.
- If a profile changes (ON8, not built), filings are not recomputed; a switch from monthly to QRMP would keep the monthly April row because it has the same period start.
- Filings are not moved to `overdue` yet (CO11).
