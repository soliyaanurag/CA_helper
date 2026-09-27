# compliance: obligations, calendar, item pages, dashboard

## Purpose
Turns a regulatory profile into dated compliance items for the 7 forms, shows them in the calendar and on the home dashboard, runs the item page (explanation, self-file path, consult-a-CA hand-off), the status lifecycle, checklists, instruction pages, peer insights and the admin editors for its config.

## What exists now
Obligation templates, the due-date calculator and filing creation work (CO1, CO2, CO3), plus a plain filings list (part of CO4) and the dashboard stub.
- **Backend:**
  - `services/compliance_service.py`: `financial_year_start()`, `fy_label()`, `periods_of_year()` (12 months, 4 quarters or the year), `due_date()` (reads the template's `due_date_rule`), `create_filings(business_id, profile, today)` (called by onboarding after registration; does not commit), `list_filings(business)`, `get_dashboard(user)` (welcome text).
  - `routes/compliance.py`: `GET /api/v1/compliance/dashboard`, `GET /api/v1/compliance/items`.
  - `schemas/compliance.py`: `ComplianceDashboardSchema`, `ComplianceItemSchema`.
  - `seed.py`: `seed_obligation_templates()` adds 9 templates for the 7 forms (GSTR-1 and GSTR-3B each have a monthly and a QRMP template), **all `TODO_VERIFY`**.
- **How filings are created:** for each template in force whose `applicability` matches the profile, one filing per period of the **current financial year**, status `upcoming`. Only periods due today or later are added (older ones may already be filed). Existing filings are skipped, so it is safe to run again.
- **Due-date rules** (JSON in `obligation_templates.due_date_rule`): monthly `{"day": 11}` = the 11th of the next month; quarterly `{"quarters": [[7, 13], [10, 13], [1, 13], [4, 13]]}` = [month, day] for Q1–Q4; yearly `{"month": 7, "day": 31}` after the financial year, with `audit_month`/`audit_day` for businesses with a tax audit (ITR).
- **Tests:** `tests/test_compliance_due_dates.py` (periods and due dates), `tests/test_compliance_items.py` (which forms for QRMP, monthly and composition businesses; only future periods; idempotent; list sorted; 404 before registration), `tests/test_compliance_dashboard.py`.
- **Frontend:** `pages/business/BusinessDashboardPage.jsx` (welcome text); "Compliance calendar" at `/business/compliance` (`pages/business/CompliancePage.jsx`) lists the filings in a table (form, period, due date, status); before registration it links to the Business profile page. `useFilings()` in `api/compliance.js` (null before registration). Test: `CompliancePage.test.jsx`. The month view comes later.
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
- `create_filings(business_id, profile, today) -> int`: add the missing filings of the current financial year (does not commit). Used by onboarding.
- `list_filings(business) -> list[ComplianceItem]`.
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
