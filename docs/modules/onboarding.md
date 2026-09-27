# onboarding: registration, regulatory profile, NIC code

## Purpose
Business registration (mandatory + conditional fields), the rule engine that derives the regulatory profile (MSME tier, GST scheme, ITR form, presumptive eligibility, tax audit, TDS returns) with a "why" for every line, NIC code selection, OCR auto-fill and the profile lifecycle check.

## What exists now
Skeleton only; no features yet.
- Backend: no code yet (no blueprint, models, schemas or services). Create `routes/onboarding.py`, `schemas/onboarding.py`, `services/onboarding_service.py` (and `models/onboarding.py`) when the first feature lands, and add the blueprint to `BLUEPRINTS` (docs/PATTERNS.md).
- Frontend: one placeholder page, "Business profile" at `/business/onboarding` (business nav), `frontend/src/pages/business/OnboardingPage.jsx`, built from `Placeholder`; no API hooks yet.
- No legal values exist yet; what needs verifying is listed in `docs/TODO_VERIFY.md`.

## Tables
Created by migration `schema: complete data model` (no service, route or page uses them yet). Columns, constraints and status values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/onboarding.py`.
- `businesses`: one live business per business user; PAN, GSTIN, TAN and phone encrypted (`EncryptedString`, not searchable, no blind index); `annual_turnover` is an amount; CHECKs for GSTIN, TAN and CIN/LLPIN
- `regulatory_profiles`: the current computed profile (1–1), with a "why" per line (`explanations`) and `rule_version`
- `nic_codes`: the official NIC list (reference data, imported, never invented)
- `rule_thresholds` (config): value, unit, `source_reference`, `effective_from`, `effective_to`; unique (key, effective_from)

## Endpoints
None yet. Planned: `/api/v1/onboarding/...` (registration, profile, re-check); admin editors at `/api/v1/admin/onboarding/...` (the rule-threshold editor is planned together with the compliance admin editors).

## Service functions other modules call
None yet. Planned: `get_business_profile(business_id)`, `get_regulatory_profile(business_id)` (used by compliance, marketplace, assistant, alerts).

## Depends on
core-auth (users), core-infra (encryption, Gemini wrapper, OCR).

## Contracts (don't change without telling the team)
- Legal thresholds come from `rule_thresholds` rows, never from code (rule 3)

## Known issues
None yet.
