# onboarding: registration, regulatory profile, NIC code

## Purpose
Business registration (mandatory + conditional fields), the rule engine that derives the regulatory profile (MSME tier, GST scheme, ITR form, presumptive eligibility, tax audit, TDS returns) with a "why" for every line, NIC code selection, OCR auto-fill and the profile lifecycle check.

## What exists now
Registration and the regulatory profile work (ON1, ON2, ON4, ON5, ON6, ON7; ON3 only format checks).
- **Backend:**
  - `routes/onboarding.py`: `POST` and `GET /api/v1/onboarding/business` (business role only).
  - `schemas/onboarding.py`: `BusinessInputSchema` (the form: format checks for PAN, GSTIN, TAN, phone and Udyam number; GSTIN required when GST registered, TAN when deducting TDS, CIN/LLPIN for LLPs and companies; codes are trimmed and capitalised; codes that do not apply are dropped), `BusinessSchema`, `RegulatoryProfileSchema`, `MyBusinessSchema`.
  - `services/onboarding_service.py`: `register_business()` saves the business, computes the profile and asks compliance to create the filings, in one commit; `compute_profile()` is the rule engine (7 numbered steps, each writing a sentence into `explanations`); `_threshold(key, today)` reads a legal value from `rule_thresholds`.
  - `seed.py`: `seed_rule_thresholds()` adds 11 thresholds, **all `TODO_VERIFY`** (`docs/TODO_VERIFY.md`).
  - PAN, GSTIN, TAN and phone are stored encrypted (`EncryptedString`).
- **Tests:** `tests/test_onboarding_register.py` (register, filings created, PAN encrypted, one per user, validation, GET, roles), `tests/test_onboarding_profile.py` (every rule of the engine, and that thresholds come from the table).
- **Frontend:** "Business profile" at `/business/onboarding` (`pages/business/OnboardingPage.jsx`): the registration form (Zod rules mirror `BusinessInputSchema`; GSTIN, composition, TAN, salary and CIN/LLPIN fields appear only when they apply) until the business is registered, then the regulatory profile with the "why" under each line, a notice when GST registration is suggested or ROC filings are not tracked, and a link to the compliance calendar. API calls in `api/onboarding.js` (`useMyBusiness()` returns null before registration, `registerBusiness()`). Test: `OnboardingPage.test.jsx`.
- **Rules in the engine** (values from `rule_thresholds`):
  1. MSME tier: the smallest tier (micro, small, medium) whose investment **and** turnover limits both fit, else `not_msme`.
  2. GST scheme: not registered → `not_registered` (and `gst_registration_suggested` above the registration limit); chose composition and within its limit → `composition`; otherwise `regular_qrmp` within the QRMP limit, else `regular_monthly`.
  3. Presumptive (44AD): individuals, proprietorships and partnership firms within the limit.
  4. Tax audit: companies always; not with the presumptive scheme; otherwise above the 44AB limit.
  5. ITR form: company → ITR-6; LLP → ITR-5; presumptive → ITR-4; other partnership → ITR-5; otherwise ITR-3.
  6. TDS: `files_26q` = deducts TDS; `files_24q` = deducts TDS and pays salaries above the limit.
  7. `roc_not_tracked` for LLPs and companies.

## Tables
Created by migration `schema: complete data model`; `businesses.gst_composition` added by `onboarding: add gst_composition to businesses`. Columns, constraints and status values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/onboarding.py`.
- `businesses`: one live business per business user; PAN, GSTIN, TAN and phone encrypted (`EncryptedString`, not searchable, no blind index); `annual_turnover` is an amount; `gst_composition` (the business chose the composition scheme); CHECKs for GSTIN, TAN and CIN/LLPIN
- `regulatory_profiles`: the current computed profile (1–1), with a "why" per line (`explanations`) and `rule_version` (`"v1"`)
- `nic_codes`: the official NIC list (reference data, imported, never invented). Empty for now.
- `rule_thresholds` (config): value, unit, `source_reference`, `effective_from`, `effective_to`; unique (key, effective_from). Seeded keys: `msme.{micro,small,medium}.max_{investment,turnover}`, `gst.registration.min_turnover`, `gst.qrmp.max_turnover`, `gst.composition.max_turnover`, `itr.presumptive_44ad.max_turnover`, `itr.audit_44ab.min_turnover`

## Endpoints
| Method | Path | Who | Returns / errors |
|---|---|---|---|
| POST | `/api/v1/onboarding/business` | business | 201 `{business, profile}` · 409 `BUSINESS_EXISTS` · 422 field errors · 500 `RULE_MISSING` (run `make seed`) |
| GET | `/api/v1/onboarding/business` | business | `{business, profile}` · 404 `BUSINESS_NOT_FOUND` |

Planned: edit + re-check (ON8), NIC suggestion; admin editors at `/api/v1/admin/onboarding/...`.

## Service functions other modules call
- `compute_profile(business, today) -> dict`: the profile values with explanations (no database writes).
- `get_my_business(business) -> {business, profile}`.
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
- ON3 is partial: formats only, no GSTIN checksum, no PAN/state cross-check.
- No edit yet (ON8): the profile and filings are computed once, at registration.
