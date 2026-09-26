# onboarding: registration, regulatory profile, NIC code

## Purpose
Business registration (mandatory + conditional fields), the rule engine that derives the regulatory profile (MSME tier, GST scheme, ITR form, presumptive eligibility, tax audit, TDS returns) with a "why" for every line, NIC code selection, OCR auto-fill and the profile lifecycle check.

## What exists now
Skeleton only; no features yet.
- Backend: no code yet (no blueprint, models, schemas or services). Create `routes/onboarding.py`, `schemas/onboarding.py`, `services/onboarding_service.py` (and `models/onboarding.py`) when the first feature lands, and add the blueprint to `BLUEPRINTS` (docs/PATTERNS.md).
- Frontend: one placeholder page, "Business profile" at `/business/onboarding` (business nav), `frontend/src/pages/business/OnboardingPage.jsx`, built from `Placeholder`; no API hooks yet.
- No legal values exist yet; what needs verifying is listed in `docs/TODO_VERIFY.md`.

## Tables
None yet. Planned:
- `businesses`: profile fields; PAN/GSTIN/TAN/phone as `EncryptedString` + blind index
- `regulatory_profiles`: computed profile lines + explanations + rule version
- `rule_thresholds` (config): value, `source_reference`, `effective_from`, `effective_to`
- `nic_codes`: reference data from the official NIC list

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
