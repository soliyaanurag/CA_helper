# onboarding: registration, regulatory profile, NIC code

## Purpose
Business registration (mandatory + conditional fields), the rule engine that derives the regulatory profile (MSME tier, GST scheme, ITR form, presumptive eligibility, tax audit, TDS returns) with a "why" for every line, NIC code selection, OCR auto-fill and the profile lifecycle check.

## What exists now
Registration, editing and the regulatory profile work (ON1–ON8).
- **Backend:**
  - `routes/onboarding.py`: `POST`, `GET` and `PUT /api/v1/onboarding/business`, `GET /api/v1/onboarding/states` (business role only).
  - **Editing (ON8):** `update_business(business, data)` saves the form, recomputes the profile in place and syncs this year's filings (`compliance_service.sync_filings()`), then returns what changed: the profile lines (codes before and after) and the filings added, reactivated, removed, moved and kept because a CA has them (`marketplace_service.open_filing_ids()`).
  - **GSTIN checks (ON3):** `app/utils/gstin.py`: the mod-36 check character, the state code must be the chosen state's, and characters 3–12 must be the PAN; one error message each. The frontend has the same checks in `lib/gstin.js`.
  - **States:** a dropdown from `content/reference/gst_states.json` (states and UTs with their GST codes, source note, **TODO_VERIFY**). `businesses.state` still holds the name; a name typed before the list existed is flagged (`state_needs_review`) and must be chosen again on the next edit.
  - **Amounts in explanations** use the Indian format (`format_inr()` in `app/utils/money.py`: ₹45,00,000).
  - `schemas/onboarding.py`: `BusinessInputSchema` (the form: format checks for PAN, GSTIN, TAN, phone and Udyam number; GSTIN required when GST registered, TAN when deducting TDS, CIN/LLPIN for LLPs and companies; codes are trimmed and capitalised; codes that do not apply are dropped), `BusinessSchema`, `RegulatoryProfileSchema`, `MyBusinessSchema`.
  - `services/onboarding_service.py`: `register_business()` saves the business, computes the profile and asks compliance to create the filings, in one commit; `compute_profile()` is the rule engine (7 numbered steps, each writing a sentence into `explanations`); `_threshold(key, today)` reads a legal value from `rule_thresholds`.
  - `seed.py`: `seed_rule_thresholds()` adds 11 thresholds, **all `TODO_VERIFY`** (`docs/TODO_VERIFY.md`).
  - PAN, GSTIN, TAN and phone are stored encrypted (`EncryptedString`).
- **Tests:** `tests/test_onboarding_register.py` (register, filings created, PAN encrypted, one per user, validation, GET, roles, each user reads only their own business), `tests/test_onboarding_profile.py` (every rule of the engine, QRMP choice, the audit split, the Indian format, thresholds from the table), `tests/test_onboarding_edit.py` (GSTIN checks with synthetic GSTINs, the state list and flag, editing: no change, monthly ↔ quarterly, filings kept when with a CA, 404 before registering).
- **Frontend:** "Business profile" at `/business/onboarding` (`pages/business/OnboardingPage.jsx`): one form registers and edits (Zod rules mirror `BusinessInputSchema`; the state is a dropdown; GSTIN, composition, "How do you file GST returns? Monthly / Quarterly (QRMP)", the other-law audit question for partnerships and LLPs, TAN, salary and CIN/LLPIN appear only when they apply; the GSTIN is checked like the server does). After registering: the profile with a row of summary chips (e.g. Micro · QRMP · ITR-4 · 26Q), every line collapsible to its "why", "Edit details", and after an edit a "What changed" box. API calls in `api/onboarding.js` (`useMyBusiness()`, `registerBusiness()`, `updateBusiness()`, `useGstStates()`). Tests: `OnboardingPage.test.jsx`, `lib/gstin.test.js`.
- **Rules in the engine** (values from `rule_thresholds`):
  1. MSME tier: the smallest tier (micro, small, medium) whose investment **and** turnover limits both fit, else `not_msme`.
  2. GST scheme: not registered → `not_registered` (and `gst_registration_suggested` above the registration limit); chose composition and within its limit → `composition`; above the QRMP limit → `regular_monthly`; within it, **the business's choice** (`gst_qrmp`): `regular_qrmp` or `regular_monthly`. The explanation says it was their choice.
  3. Presumptive (44AD): individuals, proprietorships and partnership firms within the limit.
  4. Audits, two lines: **tax audit (s.44AB)** (`audit_applicable`): not with the presumptive scheme, otherwise above the 44AB limit, for every entity type; **accounts audited under another law** (`other_audit_applicable`): companies always, partnerships and LLPs from their answer (`accounts_audited_other_law`, asked on the form with a hint that names no limit), individuals and proprietors never. The ITR due date uses **either** audit.
  5. ITR form: company → ITR-6; LLP → ITR-5; presumptive → ITR-4; other partnership → ITR-5; otherwise ITR-3.
  6. TDS: `files_26q` = deducts TDS; `files_24q` = deducts TDS and pays salaries above the limit.
  7. `roc_not_tracked` for LLPs and companies.

## Tables
Created by migration `schema: complete data model`; `businesses.gst_composition` added by `onboarding: add gst_composition to businesses`; `businesses.gst_qrmp`, `businesses.accounts_audited_other_law` and `regulatory_profiles.other_audit_applicable` by `onboarding: QRMP choice and audit under another law` (it keeps existing businesses as they were: QRMP ones count as having chosen it, companies get the other-law audit). Columns, constraints and status values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/onboarding.py`.
- `businesses`: one live business per business user; PAN, GSTIN, TAN and phone encrypted (`EncryptedString`, not searchable, no blind index); `annual_turnover` is an amount; `gst_composition` (the business chose the composition scheme), `gst_qrmp` (chose quarterly returns), `accounts_audited_other_law` (partnerships and LLPs); CHECKs for GSTIN, TAN and CIN/LLPIN
- `regulatory_profiles`: the current computed profile (1–1), with a "why" per line (`explanations`), `other_audit_applicable` and `rule_version` (`"v2"`: QRMP as a choice, the audit split)
- `nic_codes`: the official NIC list (reference data, imported, never invented). Empty for now.
- `rule_thresholds` (config): value, unit, `source_reference`, `effective_from`, `effective_to`; unique (key, effective_from). Seeded keys: `msme.{micro,small,medium}.max_{investment,turnover}`, `gst.registration.min_turnover`, `gst.qrmp.max_turnover`, `gst.composition.max_turnover`, `itr.presumptive_44ad.max_turnover`, `itr.audit_44ab.min_turnover`

## Endpoints
| Method | Path | Who | Returns / errors |
|---|---|---|---|
| POST | `/api/v1/onboarding/business` | business | 201 `{business, profile}` · 409 `BUSINESS_EXISTS` · 422 field errors · 500 `RULE_MISSING` (run `make seed`) |
| GET | `/api/v1/onboarding/business` | business | `{business, profile}`; `business.state_needs_review` · 404 `BUSINESS_NOT_FOUND` |
| PUT | `/api/v1/onboarding/business` | business | the same body as POST → `{business, profile, changes: {profile: [{line, old, new}], filings: {added, restored, removed, moved, kept_with_ca}}}` · 404 `BUSINESS_NOT_FOUND` · 422 |
| GET | `/api/v1/onboarding/states` | business | `[{name, code}]` states and UTs with their GST codes |

POST/PUT 422 messages for the GSTIN: a wrong check character, a state code that is not the chosen state's, a PAN that does not match; for the state: "Choose your state from the list."

Planned: NIC suggestion; admin editors at `/api/v1/admin/onboarding/...`.

## Service functions other modules call
- `compute_profile(business, today) -> dict`: the profile values with explanations (no database writes).
- `get_my_business(business) -> {business, profile}`.
- `get_business(business_id) -> Business | None`: one business by id (marketplace shows its name on engagements).
- `get_msme_tier(business) -> str | None`: the profile's MSME tier, e.g. `"micro"` (marketplace pro-bono eligibility).
- `get_itr_form(business) -> str | None`: the profile's ITR form code, e.g. `"itr_5"` (marketplace picks the ITR
  service for it).
- `business_of_user(user) -> Business | None`: the user's live business (marketplace ranks the CA list for it).
- `count_businesses() -> int` (admin dashboard).
- The logged-in user's business: `current_business()` in `app.utils.decorators` (core-auth).

## Depends on
core-auth (users, `current_business()`), core-infra (encryption), compliance (`create_filings()` after registering).

## Contracts (don't change without telling the team)
- Legal thresholds come from `rule_thresholds` rows, never from code (rule 3)
- `explanations` has one sentence per profile line, keyed by the column name (`msme_tier`, `gst_scheme`, ...)
- Profile codes (`msme_tier`, `gst_scheme`, `itr_form`): `docs/DATA_MODEL.md` "Status values"

## Known issues
- **Every threshold is `TODO_VERIFY`**; the values are unchecked (`docs/TODO_VERIFY.md`).
- Simplifications (the form does not ask for them yet): GST registration uses the lower (services) limit for everyone; composition uses the goods limit; presumptive uses 44AD's basic limit (no cash-receipts condition, no 44ADA for professionals, no ITR-4 income limit); tax audit ignores the higher limit for mostly digital receipts; special-category states are not handled.
- The QRMP question is shown to every regular-scheme business; above the QRMP limit the answer is ignored and the explanation says returns are monthly (the form does not know the limit, which lives in `rule_thresholds`).
- The GST state list is **TODO_VERIFY** (`docs/TODO_VERIFY.md`).
- Businesses registered before past filings existed get this year's past filings on their next "Edit details" save.
