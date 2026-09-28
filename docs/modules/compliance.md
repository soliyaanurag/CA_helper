# compliance: obligations, calendar, item pages, dashboard

## Purpose
Turns a regulatory profile into dated compliance items for the 7 forms, shows them in the calendar and on the home dashboard, runs the item page (explanation, self-file path, consult-a-CA hand-off), the status lifecycle, checklists, instruction pages, peer insights and the admin editors for its config.

## What exists now
The whole business side of a filing works: templates, due dates and filing creation (CO1–CO3), the list with filters
(CO4), the filing page (CO5) with the form's content (CO6), checklist ticks (CO7), choosing a path (CO8), marking it
filed with the acknowledgement (CO9), the status lifecycle up to `filed` (CO10), the hourly overdue job (CO11) and
the dashboard numbers (CO12). The penalty estimate on the filing page and the dashboard comes from the alerts
module (AL5; its own endpoints, shown by `FilingPage` and `BusinessDashboardPage`). Not yet: `filed_verified` (needs
OCR, DO8), peer insights (CO13).
- **Backend** (`services/compliance_service.py`, `routes/compliance.py`, `schemas/compliance.py`):
  - Filings: `financial_year_start()`, `fy_label()`, `periods_of_year()`, `due_date()` (reads the template's
    `due_date_rule`), `sync_filings(business_id, profile, today, keep_ids)` (makes this year's filings match the
    profile; used after registering and after every edit; does not commit), `create_filings()` (the same for a new
    business), `list_filings(business, status, form_code, due_from, due_to)`.
  - Dashboard (CO12): `get_dashboard(user, business, today)`: `registered`, `next_deadline` (the first not-filed
    filing due today or later), `due_this_month` (not filed, due from today to the end of the month), `overdue` (not
    filed, due date passed, whatever the status, so a late `with_ca` filing counts), `with_ca`. Before registration
    only the welcome.
  - Form content (CO6): `get_form_content(form_code)` reads `content/forms/<FOLDER>/explanation.md`,
    `instructions.md` (front matter and `<!-- -->` notes removed; Markdown) and `checklist.yaml` (PyYAML);
    `FORM_FOLDERS` maps `itr` → `ITR`, `tds_24q` → `24Q`, ... The combined `status` is the least finished of the two
    pages (`TODO` < `DRAFT` < `DONE`).
  - Filing page (CO5): `get_filing(business, item_id)` → the filing (plus `filed_at`, `acknowledgement_no`), the
    template's name, the content, the checklist with `ticked`, and the acknowledgement's file name (or null). Only the
    owner's live filings (404 `FILING_NOT_FOUND`).
  - `choose_path(business, item_id, path)` (CO8): `self` or `ca`, while the filing is not with a CA or filed (409
    `FILING_LOCKED`). Choosing `ca` does not change the status; `with_ca` comes from an active engagement.
  - `set_checklist_tick(business, item_id, key, ticked)` (CO7): a tick is a `checklist_ticks` row, unticking deletes
    it; 422 `UNKNOWN_CHECKLIST_KEY`. Then the status is worked out again (CO10, `_refresh_status`): past due →
    `overdue`; nothing ticked → `upcoming`; some ticked, a required one missing → `docs_pending`; every required one
    ticked → `ready`. `with_ca`, `filed` and `filed_verified` never change here.
  - `mark_filed(business, user, item_id, acknowledgement_no, upload)` (CO9): from `upcoming`, `docs_pending`, `ready`
    or `overdue` → `filed`, path `self`, `filed_at` now; the ARN is trimmed and capitalised; the optional file is
    stored encrypted as a `documents` row (type `acknowledgement`, with `fy` and `period_label`) linked through
    `compliance_items.acknowledgement_document_id`. 409 `FILING_WITH_CA` (the CA marks it, CW5), 409 `ALREADY_FILED`;
    storage errors pass through and nothing is saved.
  - `unmark_filed(business, item_id)`: undoes a mistaken self-filed mark (status worked out again, ARN, `filed_at`
    and the acknowledgement removed; the document is soft-deleted). 409 `NOT_SELF_FILED`.
  - `get_acknowledgement(business, item_id)` → (document, bytes) for the download (404 `ACKNOWLEDGEMENT_MISSING`).
  - `mark_overdue_filings(today)` (CO11): live filings in `upcoming`, `docs_pending` or `ready` whose due date is
    before today become `overdue` (a filing due today is not late yet; `with_ca`, filed and removed filings are
    untouched; commits once, returns the count).
  - `seed.py`: `seed_obligation_templates()` adds 9 templates for the 7 forms, **all `TODO_VERIFY`**.
- **How filings are made (`sync_filings`):** for each template in force whose `applicability` matches the profile,
  one filing per period of the **current financial year, from 1 April**; a period whose due date has passed starts
  as `overdue` (the business may have filed it before joining; it can mark it filed), the rest `upcoming`. On a
  profile change: a filing that no longer applies is soft-deleted unless it is filed, `with_ca` or in an open
  engagement; one that applies again is reactivated (never inserted twice); a not-started filing whose period or due
  date changed gets the new one. Running it again changes nothing.
- **Due-date rules** (JSON in `obligation_templates.due_date_rule`): monthly `{"day": 11}` = the 11th of the next
  month; quarterly `{"quarters": [[7, 13], [10, 13], [1, 13], [4, 13]]}` = [month, day] for Q1–Q4; yearly
  `{"month": 7, "day": 31}` after the financial year, with `audit_month`/`audit_day` for businesses with an audit
  (ITR).
- **Worker:** `backend/worker.py` runs `mark_overdue_filings` every hour (id `compliance.mark_overdue`;
  `make dev-worker`).
- **Content:** `content/forms/<FORM>/` has a **first draft** (`status: DRAFT`) of the explanation, the self-filing
  steps and the document checklist of each of the 7 forms (no amounts, rates or due dates). Someone must review
  them against the official sources and set `status: DONE`.
- **Frontend:**
  - `pages/business/FilingPage.jsx` at `/business/compliance/:itemId`: header (form, period, status badge, due
    date and days left); "How will you file it?" (buttons for `self` / `ca`; with `ca`, a link to the marketplace
    with the form's service pre-selected, none for ITR; with `self`, the "Mark as filed" form with the optional ARN
    and file); "With a CA" instead when the filing is in an open engagement or `with_ca` (the CA's name from
    `useMyEngagements()`); "Filed" once filed (date, ARN, "Open the acknowledgement", "Undo: not filed yet"); the
    checklist ("n of m required documents ready"; under each entry its linked files and "Add a file", from the
    documents module); the guide with two tabs (steps / what is this form), shown with
    `components/Markdown.jsx` (react-markdown), and a "draft" note while the content is not `DONE`.
  - `pages/business/CompliancePage.jsx`: filter chips, "Earlier this year" and one table per month; the form name
    links to the filing page.
  - `pages/business/BusinessDashboardPage.jsx`: the four cards use `GET /compliance/dashboard`; the to-do list
    (from filings and engagements) links "Decide how to file ..." to the filing page.
  - `api/compliance.js`: `useComplianceDashboard`, `useFilings`, `useFiling`, `chooseFilingPath`, `tickChecklist`,
    `markFiled`, `unmarkFiled`, `useAcknowledgementFile`.
- **Tests:** backend `test_compliance_filing_page.py` (detail, another business's filing 404, path + lock,
  ticks → docs pending → ready → upcoming, overdue stays overdue, unknown key, mark filed with and without a file,
  download, wrong file type changes nothing, twice / with a CA refused, undo, list filters),
  `test_compliance_forms.py` (every form has texts without front matter or notes, a checklist with unique keys and
  a required entry; 404; any role), `test_compliance_dashboard.py` (numbers, filed not counted, with a CA counted,
  unregistered), `test_compliance_overdue.py`, `test_compliance_due_dates.py`, `test_compliance_items.py`;
  frontend `FilingPage.test.jsx`, `CompliancePage.test.jsx`, `BusinessDashboardPage.test.jsx`.

## Tables
Created by migration `schema: complete data model`. Columns, constraints and status values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/compliance.py`.
- `obligation_templates` (config): form code, frequency, applicability and due-date rule (JSONB), `source_reference`, `effective_from/to`. Seeded (9 rows).
- `compliance_items`: one filing per business, form and period (partial unique index on live rows), status, filing path, nil return, acknowledgement number and document
- `checklist_ticks`: ticked checklist keys (from `content/forms/<FORM>/checklist.yaml`); unticking deletes the row.

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/v1/compliance/dashboard` | business | `{message, registered, next_deadline (a filing or null), due_this_month, overdue, with_ca}` |
| GET | `/api/v1/compliance/items` | business | the business's filings, soonest due first: `id, form_code, fy, period_label, period_start, period_end, due_date, status, filing_path`; optional `?status=&form_code=&due_from=&due_to=` · 404 `BUSINESS_NOT_FOUND` |
| GET | `/api/v1/compliance/items/{id}` | business | `{filing (+ filed_at, acknowledgement_no), form_name, content_status, explanation, instructions, checklist [{key, label, required, help, ticked}], acknowledgement {filename, uploaded_at} or null}` · 404 `FILING_NOT_FOUND` |
| POST | `/api/v1/compliance/items/{id}/path` | business | `{path: "self" \| "ca"}` → the filing page · 409 `FILING_LOCKED` |
| POST | `/api/v1/compliance/items/{id}/checklist` | business | `{key, ticked}` → the filing page · 422 `UNKNOWN_CHECKLIST_KEY` |
| POST | `/api/v1/compliance/items/{id}/mark-filed` | business | multipart: `acknowledgement_no` and `file` (both optional) → the filing page · 409 `FILING_WITH_CA`, `ALREADY_FILED` · storage errors (`FILE_TYPE_NOT_ALLOWED`, `FILE_TOO_LARGE`, `FILE_EMPTY`) |
| POST | `/api/v1/compliance/items/{id}/unmark-filed` | business | → the filing page · 409 `NOT_SELF_FILED` |
| GET | `/api/v1/compliance/items/{id}/acknowledgement` | business | the file · 404 `ACKNOWLEDGEMENT_MISSING` |
| GET | `/api/v1/compliance/forms/{form_code}` | any logged-in user | `{form_code, status, explanation, instructions, checklist}` · 404 `FORM_NOT_FOUND` |

Planned: admin editors at `/api/v1/admin/compliance/...`; the CA's side of a filing (CW3, CW5).

## Service functions other modules call
- `sync_filings(business_id, profile, today, keep_ids=()) -> dict`: make this year's filings match the profile (see above; does not commit). Used by onboarding after an edit; `keep_ids` are filings in an open engagement.
- `create_filings(business_id, profile, today) -> int`: `sync_filings` for a new business, returns how many were added (does not commit). Used by onboarding after registering.
- `list_filings(business, status=None, form_code=None, due_from=None, due_to=None) -> list[ComplianceItem]`.
- `get_form_content(form_code) -> dict`: a form's Markdown texts and checklist (for the CA workspace and the assistant later).
- `list_unfiled_filings_due_by(day) -> list[ComplianceItem]`: every business's live, not-filed filings due on or
  before `day`, soonest first. Used by the alerts reminder job.
- `get_filings_by_ids(filing_ids, lock=False) -> {id: ComplianceItem}`: live filings by id; `lock=True` is
  `SELECT ... FOR UPDATE` until the caller commits (does not commit). Used by marketplace (engagements).
- `mark_filings_with_ca(filing_ids)`: status `with_ca`, filing path `ca` (does not commit). Called by marketplace
  when an engagement becomes `active` (the CA accepts, or the business accepts a quote).
- `checklist_keys(form_code) -> list[str]`, `tick_checklist_entry(filing, key)` (tick + status again, does not
  commit, 422 `UNKNOWN_CHECKLIST_KEY`) and `filings_by_acknowledgement(document_ids) -> {document id: filing}`.
  Used by documents (a linked file ticks its checklist entry; an acknowledgement cannot be deleted from the vault).
- `due_date(template, period_end, quarter, audit) -> date`, `financial_year_start(day)`, `periods_of_year(frequency, fy_start)`.

## Depends on
onboarding (the regulatory profile, passed in by `register_business()`), core-auth (`current_business()`, `current_business_or_none()`), documents (`documents_service.add_document / read_document / remove_document` for the acknowledgement), marketplace (`with_ca` status from engagements; the frontend reads `my-engagements`).

## Contracts (don't change without telling the team)
- Status codes: `upcoming → docs_pending → ready → with_ca → filed → filed_verified`, plus `overdue` from the states before `with_ca` (codes and labels: `docs/DATA_MODEL.md`, "Status values"). `docs_pending` / `ready` follow the required checklist entries
- Checklist keys in `checklist.yaml` are stored in `checklist_ticks`: never rename a key once used
- `GET /api/v1/compliance/dashboard` is the business home page's data (frontend `/business`)
- Form codes: `itr`, `gstr_1`, `gstr_3b`, `cmp_08`, `gstr_4`, `tds_24q`, `tds_26q` (`FormCode`; folders in `content/forms/` use the display names)
- Template `applicability` keys are `regulatory_profiles` column names; `{}` means every business
- Period labels: `"Apr 2026"` (monthly), `"Q1 2026-27"` (quarterly), `"FY 2026-27"` (yearly)

## Known issues
- **Every due-date rule is `TODO_VERIFY`** (`docs/TODO_VERIFY.md`); GSTR-3B QRMP uses the 22nd for every state (some states have the 24th).
- Only the current financial year is created; nothing creates next year's filings yet (a worker job, X2/ON14).
- The yearly ITR filing is the current year's (FY 2026-27, due in 2027); last year's return is not added.
- A late `with_ca` filing keeps `with_ca` (not `overdue`); `SCOPE.md` says overdue is reachable from any pre-filed state. See `DECISIONS.md` (2026-09-28).
- **The form content is a first draft** (`status: DRAFT`), not checked against the official sources yet.
- `filed_verified` is never set yet: it needs the acknowledgement OCR (DO8).
- A CA cannot open a filing page yet, and cannot mark a filing filed (CW3, CW5); a `with_ca` filing can only be finished by the CA.
- The penalty figures are "pending" until the `penalty_rules` amounts are verified (alerts, `docs/TODO_VERIFY.md`).
