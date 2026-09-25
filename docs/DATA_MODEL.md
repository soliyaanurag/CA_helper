# Data model

> **DRAFT: planned tables, not built yet.** No migration exists yet, so there are no tables. Each PR that adds a
> migration updates this file to match reality. Column lists are indicative; the module that holds the table
> decides details.

## Global rules (from CLAUDE.md)
- Soft delete only: `is_active` + `deleted_at` on user-facing entities.
- Timestamps: timezone-aware UTC (`created_at`, `updated_at`); display in Asia/Kolkata.
- Money: `Numeric(12, 2)` rupees ↔ Python `Decimal`.
- Financial year: April–March, stored as a string like `2026-27`.
- Sensitive fields (PAN, GSTIN, TAN, phone) use `EncryptedString` plus a `<field>_bidx` blind index (HMAC-SHA256)
  for uniqueness and lookups. Passwords are argon2 hashes. Uploaded files are encrypted on disk; only metadata is in the DB.
- Legal rules are **data**: every config table with thresholds, due-date rules or rates has `source_reference`,
  `effective_from`, `effective_to`. Unverified values have `TODO_VERIFY` in `source_reference` and are listed
  in `docs/TODO_VERIFY.md`.
- Constraint/index names are generated from the naming convention in `backend/app/core/db/base.py`.
- A module never imports another module's models; it calls that module's service functions.

## Planned tables

| Table | Module | One row is... | Key columns (indicative) |
|---|---|---|---|
| `users` | core/auth | a login account | email (unique), password_hash, role, email_verified, is_active, deleted_at |
| `email_otps` | core/auth | a one-time code | user_id, purpose (verify/reset), code_hash, expires_at, attempts, used_at |
| `notifications` | core/notifications | a tray entry | user_id, type, title, body, link, read_at, created_at |
| `businesses` | onboarding | a registered business | user_id, legal_name, entity_type, state, description, turnover_range, investment_amount, pan (enc) + pan_bidx, gst_registered, gstin (enc) + gstin_bidx, tan (enc), deducts_tds, pays_salary_above_limit, cin_llpin, udyam_number, phone (enc), nic_code |
| `regulatory_profiles` | onboarding | the computed profile of a business | business_id, msme_tier, gst_scheme, itr_form, presumptive_eligible, audit_applicable, tds_returns, explanations (JSON), rule_version, computed_at |
| `rule_thresholds` | onboarding | one legal threshold/value | key, value, unit, source_reference, effective_from, effective_to |
| `nic_codes` | onboarding | an official NIC activity code | code, description, section/division |
| `obligation_templates` | compliance | how a form applies and when it is due | form_code, applicability (JSON), frequency, due_date_rule (JSON), source_reference, effective_from, effective_to |
| `compliance_items` | compliance | one filing for one period | business_id, form_code, fy, period_start, period_end, due_date, status, path (self/ca), filed_at, ack_document_id |
| `checklist_ticks` | compliance | a ticked checklist entry | item_id, checklist_key, ticked_at |
| `reminder_log` | alerts | a reminder already sent | item_id, kind (T-7/T-3/T-1/overdue), sent_at |
| `notification_settings` | alerts | a user's email preference per type | user_id, type, email_enabled |
| `penalty_rules` | alerts | late fee / interest rule | form_code, late_fee_per_day, max_late_fee, interest_rate, source_reference, effective_from, effective_to |
| `documents` | documents | an uploaded file (metadata) | business_id, uploaded_by, fy, period, doc_type, storage_key, mime_type, size, sha256, ocr_status, ocr_fields (JSON), is_active, deleted_at |
| `kb_chunks` | assistant | a knowledge-base chunk | source, title, url, text, embedding `vector(N)` |
| `chat_messages` | assistant | an assistant message | user_id, role, content, citations (JSON) |
| `news_sources` | regulatory | a configured source | name, url, kind (rss/html), enabled |
| `news_articles` | regulatory | a scraped article | source_id, url, title, published_at, content_hash, fetched_at |
| `regulatory_changes` | regulatory | an extracted change awaiting approval | article_id, change_type, forms, categories, dates (JSON), status, approved_by, approved_at |
| `ca_profiles` | marketplace | a CA's practice profile | user_id, membership_no, cop_number, verified, city, languages, specializations, capacity, pro_bono_pledge |
| `service_catalog` | marketplace | a standard service | code, form_code, name, typical_min, typical_max |
| `ca_services` | marketplace | a CA's price for a catalog service | ca_id, service_code, price |
| `engagements` | marketplace | a business–CA request/engagement | business_id, ca_id, form_code/item_id, status, quote_amount, quote_reason, expires_at |
| `ratings` | marketplace | a review after completion | engagement_id, stars, review |
| `client_invites` | marketplace | a CA's invite to an existing client | ca_id, email, token, status |
| `document_requests` | ca_workspace | a CA's request for a document | engagement_id, item_id, doc_type, message, status |
| `ca_notes` | ca_workspace | a private CA note | ca_id, business_id, text |
| `admin_audit_log` | admin | an admin action | admin_id, action, target_type, target_id, details (JSON) |

## Status values

This section is the one authoritative list of these values. Module docs and code refer here; changing a value
means telling the team (it is a contract). Stored codes are fixed by the migration that creates the column and
are recorded here in the same PR.

**`compliance_items.status`** (compliance)

| Value | Notes |
|---|---|
| `Upcoming` | initial state |
| `Docs pending` | |
| `Ready` | |
| `With CA` | set from marketplace engagements |
| `Filed` | |
| `Filed–verified` | acknowledgement verified (OCR) |
| `Overdue` | reachable from any pre-filed state |

Lifecycle: `Upcoming → Docs pending → Ready → With CA → Filed → Filed–verified`, plus `Overdue` from any pre-filed state.

**`engagements.status`** (marketplace)

| Value | Notes |
|---|---|
| `Requested` | initial state |
| `Accepted` | |
| `Quoted` | revised quote sent (reason required) |
| `Active` | |
| `Completed` | |
| `Declined` | the CA declined the request |
| `Expired` | the request auto-expired after 48 hours; the business is re-matched |

Lifecycle: `Requested → Accepted/Quoted → Active → Completed`, plus `Declined` / `Expired`.

## Cross-module dependencies to watch
- `ca_has_active_access` (core/permissions) needs engagement status from marketplace → a marketplace
  service function, not a model import.
- Compliance status "With CA" (compliance) comes from marketplace engagements (marketplace).
- Documents (documents) are attached to compliance items (compliance) and used by ca_workspace.
- CA urgency (ca_workspace) takes input from regulatory changes (regulatory) and compliance items (compliance).
