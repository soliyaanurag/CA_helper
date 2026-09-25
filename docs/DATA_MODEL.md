# Data model

> **DRAFT: planned tables, not built yet.** Phase 0 created no tables. Phase 1 (and each later PR that adds a
> migration) updates this file to match reality. Column lists are indicative; the owning module decides details.

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

| Table | Owner (module) | One row is... | Key columns (indicative) | Task |
|---|---|---|---|---|
| `users` | A (core/auth) | a login account | email (unique), password_hash, role, email_verified, is_active, deleted_at | AUTH-01 |
| `email_otps` | A (core/auth) | a one-time code | user_id, purpose (verify/reset), code_hash, expires_at, attempts, used_at | AUTH-02 |
| `notifications` | B (core/notifications) | a tray entry | user_id, type, title, body, link, read_at, created_at | INF-05 |
| `businesses` | A (onboarding) | a registered business | user_id, legal_name, entity_type, state, description, turnover_range, investment_amount, pan (enc) + pan_bidx, gst_registered, gstin (enc) + gstin_bidx, tan (enc), deducts_tds, pays_salary_above_limit, cin_llpin, udyam_number, phone (enc), nic_code | ONB-01 |
| `regulatory_profiles` | A (onboarding) | the computed profile of a business | business_id, msme_tier, gst_scheme, itr_form, presumptive_eligible, audit_applicable, tds_returns, explanations (JSON), rule_version, computed_at | ONB-02 |
| `rule_thresholds` | A (onboarding) | one legal threshold/value | key, value, unit, source_reference, effective_from, effective_to | ONB-02/04 |
| `nic_codes` | A (onboarding) | an official NIC activity code | code, description, section/division | ONB-07 |
| `obligation_templates` | A (compliance) | how a form applies and when it is due | form_code, applicability (JSON), frequency, due_date_rule (JSON), source_reference, effective_from, effective_to | COM-01 |
| `compliance_items` | A (compliance) | one filing for one period | business_id, form_code, fy, period_start, period_end, due_date, status, path (self/ca), filed_at, ack_document_id | COM-01 |
| `checklist_ticks` | A (compliance) | a ticked checklist entry | item_id, checklist_key, ticked_at | COM-06 |
| `reminder_log` | B (alerts) | a reminder already sent | item_id, kind (T-7/T-3/T-1/overdue), sent_at | ALR-01/02 |
| `notification_settings` | B (alerts) | a user's email preference per type | user_id, type, email_enabled | ALR-03 |
| `penalty_rules` | B (alerts) | late fee / interest rule | form_code, late_fee_per_day, max_late_fee, interest_rate, source_reference, effective_from, effective_to | ALR-04 |
| `documents` | B (documents) | an uploaded file (metadata) | business_id, uploaded_by, fy, period, doc_type, storage_key, mime_type, size, sha256, ocr_status, ocr_fields (JSON), is_active, deleted_at | DOC-01 |
| `kb_chunks` | B (assistant) | a knowledge-base chunk | source, title, url, text, embedding `vector(N)` | AST-02 |
| `chat_messages` | B (assistant) | an assistant message | user_id, role, content, citations (JSON) | AST-05 |
| `news_sources` | B (regulatory) | a configured source | name, url, kind (rss/html), enabled | REG-01 |
| `news_articles` | B (regulatory) | a scraped article | source_id, url, title, published_at, content_hash, fetched_at | REG-01 |
| `regulatory_changes` | B (regulatory) | an extracted change awaiting approval | article_id, change_type, forms, categories, dates (JSON), status, approved_by, approved_at | REG-02/03 |
| `ca_profiles` | C (marketplace) | a CA's practice profile | user_id, membership_no, cop_number, verified, city, languages, specializations, capacity, pro_bono_pledge | MKT-01 |
| `service_catalog` | C (marketplace) | a standard service | code, form_code, name, typical_min, typical_max | MKT-04 |
| `ca_services` | C (marketplace) | a CA's price for a catalog service | ca_id, service_code, price | MKT-04 |
| `engagements` | C (marketplace) | a business–CA request/engagement | business_id, ca_id, form_code/item_id, status, quote_amount, quote_reason, expires_at | MKT-03/06 |
| `ratings` | C (marketplace) | a review after completion | engagement_id, stars, review | MKT-10 |
| `client_invites` | C (marketplace) | a CA's invite to an existing client | ca_id, email, token, status | MKT-12 |
| `document_requests` | C (ca_workspace) | a CA's request for a document | engagement_id, item_id, doc_type, message, status | CAW-03 |
| `ca_notes` | C (ca_workspace) | a private CA note | ca_id, business_id, text | CAW-07 |
| `admin_audit_log` | C (admin) | an admin action | admin_id, action, target_type, target_id, details (JSON) | ADM-04 |

## Cross-owner dependencies to watch
- `ca_has_active_access` (A, core/permissions) needs engagement status from marketplace (C) → a marketplace
  service function, not a model import.
- Compliance status "With CA" (A) comes from marketplace engagements (C).
- Documents (B) are attached to compliance items (A) and used by ca_workspace (C).
- CA urgency (C) takes input from regulatory changes (B) and compliance items (A).
