# onboarding: registration, regulatory profile, NIC code

## Purpose
Business registration (mandatory + conditional fields), the rule engine that derives the regulatory profile (MSME tier, GST scheme, ITR form, presumptive eligibility, tax audit, TDS returns) with a "why" for every line, NIC code selection, OCR auto-fill and the profile lifecycle check.

## Owner
Member A (Business domain)

Folders: `backend/app/modules/onboarding/`, `frontend/src/features/onboarding/`

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [ ] ONB-01 · P1 · A · Registration form (mandatory + conditional fields) → business profile
- [ ] ONB-02 · P1 · A · Rule engine v0 (GST status → GST forms, entity type → ITR form, TDS answers → 24Q/26Q), placeholder values marked TODO_VERIFY
- [ ] ONB-03 · P1 · A · Basic profile page
- [ ] ONB-04 · P2 · A · Rule engine with verified thresholds in versioned rule tables (MSME tier, QRMP, composition, presumptive, audit)
- [ ] ONB-05 · P2 · A · "Why" explanation per profile line + profile review screen + edit & re-check
- [ ] ONB-06 · P2 · A · PAN/GSTIN format + checksum validation, derive state and PAN from GSTIN
- [ ] ONB-07 · P3 · A · NIC keyword shortlist + Gemini pick + user confirmation
- [ ] ONB-08 · P3 · A · OCR auto-fill from GST certificate/PAN at registration
- [ ] ONB-09 · P4 · A · Profile lifecycle check (FY start + threshold crossing)
- [ ] ONB-10 · P5 · A · NIC evaluation on ~100 labelled descriptions (top-1/top-3 accuracy)

## Tables owned
- `businesses` (planned): profile fields; PAN/GSTIN/TAN/phone as `EncryptedString` + blind index
- `regulatory_profiles` (planned): computed profile lines + explanations + rule version
- `rule_thresholds` (planned config table): value, `source_reference`, `effective_from`, `effective_to`
- `nic_codes` (planned reference data from the official NIC list)

## Endpoints exposed
Planned: `/api/onboarding/...` (registration, profile, re-check); admin editors at `/api/admin/onboarding/...` (COM-10 covers rule editors).

## Service functions others may call
- Planned: `get_business_profile(business_id)`, `get_regulatory_profile(business_id)` (used by compliance, marketplace, assistant, alerts)

## Depends on
core-auth (users), core-infra (encryption, Gemini wrapper, OCR).

## Contracts others rely on
- Legal thresholds come from `rule_thresholds` rows, never from code (rule 3)

## Known issues
_None yet._

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0: created this doc and its task list.
