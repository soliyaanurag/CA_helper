# onboarding: registration, regulatory profile, NIC code

## Purpose
Business registration (mandatory + conditional fields), the rule engine that derives the regulatory profile (MSME tier, GST scheme, ITR form, presumptive eligibility, tax audit, TDS returns) with a "why" for every line, NIC code selection, OCR auto-fill and the profile lifecycle check.

## What exists now
Registration, editing and the regulatory profile work (ON1–ON8), the NIC activity code (ON9, ON10) and OCR auto-fill (ON13).
- **Backend:**
  - `routes/onboarding.py`: `POST`, `GET` and `PUT /api/v1/onboarding/business`, `GET /api/v1/onboarding/states` (business role only).
  - **Editing (ON8):** `update_business(business, data)` saves the form, recomputes the profile in place and syncs this year's filings (`compliance_service.sync_filings()`), then returns what changed: the profile lines (codes before and after) and the filings added, reactivated, removed, moved and kept because a CA has them (`marketplace_service.open_filing_ids()`).
  - **OCR auto-fill (ON13):** `POST /api/v1/onboarding/autofill` (multipart `file`, business role, 10 per minute) → `read_registration_document(upload)`: the upload checks (`storage.check_file`), local OCR (`utils/ocr.py`) and `document_text.read_registration()` → `{found: {pan?, gstin?, legal_name?, state?, entity_type?}}`. The file is read in memory and **never stored**; nothing is saved to the business. 422 `DOCUMENT_UNREADABLE`. Frontend: "Fill in from your GST certificate or PAN card" at the top of the registration form (not when editing) fills the found fields (and ticks "GST registered" when a GSTIN was found) and says which, so the user checks them.
  - **GSTIN checks (ON3):** `app/utils/gstin.py`: the mod-36 check character, the state code must be the chosen state's, and characters 3–12 must be the PAN; one error message each. The frontend has the same checks in `lib/gstin.js`.
  - **States:** a dropdown from `content/reference/gst_states.json` (states and UTs with their GST codes, checked against the GST e-invoice portal's state codes). `businesses.state` still holds the name; a name typed before the list existed is flagged (`state_needs_review`) and must be chosen again on the next edit.
  - **Amounts in explanations** use the Indian format (`format_inr()` in `app/utils/money.py`: ₹45,00,000).
  - `schemas/onboarding.py`: `BusinessInputSchema` (the form: format checks for PAN, GSTIN, TAN, phone and Udyam number; GSTIN required when GST registered, TAN when deducting TDS, CIN/LLPIN for LLPs and companies; codes are trimmed and capitalised; codes that do not apply are dropped), `BusinessSchema`, `RegulatoryProfileSchema`, `MyBusinessSchema`.
  - `services/onboarding_service.py`: `register_business()` saves the business, computes the profile and asks compliance to create the filings, in one commit; `compute_profile()` is the rule engine (7 numbered steps, each writing a sentence into `explanations`); `_threshold(key, today)` reads a legal value from `rule_thresholds`.
  - `seed.py`: `seed_rule_thresholds()` adds 11 thresholds, each with its official source (checked on 29 Sep 2026, `docs/TODO_VERIFY.md` "Verified values"); re-running it updates rows seeded earlier.
  - PAN, GSTIN, TAN and phone are stored encrypted (`EncryptedString`).
- **NIC code (ON9, ON10):** `nic_codes` holds the 1,165 official 5-digit NIC-2008 codes from `content/reference/nic_2008.csv` (Ministry of MSME, PMEGP; source notes at the top of the file), loaded by `make seed` (`seed_nic_codes()`). `shortlist_nic_codes(description)`: the 15 codes whose description best matches the words of the business description (personal data and common words removed, plural "s" ignored, 3-letter words only as whole words; each matching word adds 1 / number of codes containing it). `suggest_nic_codes(business)`: Gemini (`app/utils/gemini_client.py`) picks the best 3 from the shortlist with a reason; codes outside the shortlist or repeated are dropped and keyword matches fill up to 3 (`source` "ai" or "keywords"); without Gemini, keyword matches only (`ai_used` false). Only the scrubbed description and the shortlist are sent. `search_nic_codes(q)` (code or words, at most 20), `set_nic_code(business, code)` (422 `UNKNOWN_NIC_CODE`). The frontend card "Business activity (NIC code)" on the profile page (`pages/business/NicCodeCard.jsx`): Suggest codes → radio options with reason and label ("AI suggestion, please check" / "Keyword match") → or search → Confirm. The description field's hint asks users to leave out names and contact details.
- **Tests:** `tests/test_onboarding_nic.py` (seed: 5-digit codes, leading zero, twice; shortlist ranking and common words; AI picks, invented/repeated codes dropped, scrubbed prompt without name or PAN, non-JSON reply, no Gemini; search; save and read back; unknown code; 404 before registering; roles; rate limit), frontend `NicCodeCard.test.jsx`; `tests/test_onboarding_register.py` (register, filings created, PAN encrypted, one per user, validation, GET, roles, each user reads only their own business), `tests/test_onboarding_profile.py` (every rule of the engine, QRMP choice, the audit split, the Indian format, thresholds from the table), `tests/test_onboarding_edit.py` (GSTIN checks with synthetic GSTINs, the state list and flag, editing: no change, monthly ↔ quarterly, filings kept when with a CA, 404 before registering).
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
- `nic_codes`: the official NIC list (reference data, imported, never invented): 1,165 five-digit NIC-2008 codes loaded by `make seed` from `content/reference/nic_2008.csv`
- `rule_thresholds` (config): value, unit, `source_reference`, `effective_from`, `effective_to`; unique (key, effective_from). Seeded keys: `msme.{micro,small,medium}.max_{investment,turnover}`, `gst.registration.min_turnover`, `gst.qrmp.max_turnover`, `gst.composition.max_turnover`, `itr.presumptive_44ad.max_turnover`, `itr.audit_44ab.min_turnover`

## Endpoints
| Method | Path | Who | Returns / errors |
|---|---|---|---|
| POST | `/api/v1/onboarding/business` | business | 201 `{business, profile}` · 409 `BUSINESS_EXISTS` · 422 field errors · 500 `RULE_MISSING` (run `make seed`) |
| GET | `/api/v1/onboarding/business` | business | `{business, profile}`; `business.state_needs_review` · 404 `BUSINESS_NOT_FOUND` |
| PUT | `/api/v1/onboarding/business` | business | the same body as POST → `{business, profile, changes: {profile: [{line, old, new}], filings: {added, restored, removed, moved, kept_with_ca}}}` · 404 `BUSINESS_NOT_FOUND` · 422 |
| GET | `/api/v1/onboarding/states` | business | `[{name, code}]` states and UTs with their GST codes |
| POST | `/api/v1/onboarding/nic-suggestions` | business | `{picks: [{code, description, reason, source: "ai" \| "keywords"}] (≤3), shortlist: [{code, description}], ai_used}` (nothing saved) · 404 `BUSINESS_NOT_FOUND` · 429 (10 per minute) |
| GET | `/api/v1/onboarding/nic-codes?q=` | business | `[{code, description}]`, at most 20 (fewer than 2 characters → `[]`) |
| PUT | `/api/v1/onboarding/business/nic-code` | business | body `{code}` → `{code, description}` · 404 `BUSINESS_NOT_FOUND` · 422 `UNKNOWN_NIC_CODE` |
| POST | `/api/v1/onboarding/autofill` | business, 10 per minute | multipart `file` (GST certificate or PAN card) → `{found: {pan?, gstin?, legal_name?, state?, entity_type?}}` · 400 `FILE_EMPTY`, `FILE_TYPE_NOT_ALLOWED`, `FILE_TOO_LARGE` · 422 `DOCUMENT_UNREADABLE`; nothing is stored |

`GET`, `POST` and `PUT /onboarding/business` also return `nic_code: {code, description}` or `null`.

POST/PUT 422 messages for the GSTIN: a wrong check character, a state code that is not the chosen state's, a PAN that does not match; for the state: "Choose your state from the list."

Planned: admin editors at `/api/v1/admin/onboarding/...`.

## Service functions other modules call
- `compute_profile(business, today) -> dict`: the profile values with explanations (no database writes).
- `resync_all_filings(today=None) -> dict`: every business's filings matched to the current obligation templates with
  its saved profile (`sync_filings`, filings in open engagements kept; no commit). The last step of `flask seed`.
- `get_my_business(business) -> {business, profile}`.
- `get_business(business_id) -> Business | None`: one business by id (marketplace shows its name on engagements).
- `get_msme_tier(business) -> str | None`: the profile's MSME tier, e.g. `"micro"` (marketplace pro-bono eligibility).
- `get_itr_form(business) -> str | None`: the profile's ITR form code, e.g. `"itr_5"` (marketplace picks the ITR
  service for it).
- `business_of_user(user) -> Business | None`: the user's live business (marketplace ranks the CA list for it).
- `count_businesses() -> int` (admin dashboard).
- The logged-in user's business: `current_business()` in `app.utils.decorators` (core-auth).

## Depends on
core-auth (users, `current_business()`), core-infra (encryption, Gemini client), compliance (`create_filings()` after registering).

## Contracts (don't change without telling the team)
- Legal thresholds come from `rule_thresholds` rows, never from code (rule 3)
- NIC codes come only from `content/reference/nic_2008.csv`; a suggested code is always one from the table (Gemini only chooses)
- `explanations` has one sentence per profile line, keyed by the column name (`msme_tier`, `gst_scheme`, ...)
- Profile codes (`msme_tier`, `gst_scheme`, `itr_form`): `docs/DATA_MODEL.md` "Status values"

## Known issues
- NIC list gaps (as in the source): some descriptions are cut off (`docs/TODO_VERIFY.md`); some activities are absent (e.g. crop growing, sale of motor vehicles), so such a business picks the closest code.
- The keyword shortlist only finds codes that share words with the description ("kirana" matches nothing; "grocery" matches little); Gemini can only choose from what it finds.
- The thresholds are verified but simplified: the lower (services) GST registration limit, the goods composition limit and the ₹2 crore / ₹1 crore limits of 44AD / 44AB are used for everyone (`docs/TODO_VERIFY.md`, "Simplifications").
- Simplifications (the form does not ask for them yet): GST registration uses the lower (services) limit for everyone; composition uses the goods limit; presumptive uses 44AD's basic limit (no cash-receipts condition, no 44ADA for professionals, no ITR-4 income limit); tax audit ignores the higher limit for mostly digital receipts; special-category states are not handled.
- The QRMP question is shown to every regular-scheme business; above the QRMP limit the answer is ignored and the explanation says returns are monthly (the form does not know the limit, which lives in `rule_thresholds`).
- Businesses registered before past filings existed get this year's past filings on their next "Edit details" save.
