# Data model

> **Mostly planned.** Implemented tables are marked **(implemented)** and list their real columns; the rest are
> planned and indicative. Each PR that adds a migration updates this file to match reality. The module that holds
> a table decides its details.

## Global rules (from CLAUDE.md)
- Every model subclasses `BaseModel` (`backend/app/models/base.py`): primary key `id` is a **UUID** (uuid4,
  generated in Python, Postgres `uuid` type); foreign keys are therefore UUID columns too.
- Timestamps: every table has `created_at` and `updated_at` (`TimestampMixin`), timezone-aware UTC, with a
  database default `now()`; display in Asia/Kolkata.
- Soft delete only: user-facing entities add `SoftDeleteMixin` (`is_active` default true + `deleted_at`).
- Enums: Python `StrEnum` with lowercase snake_case values, stored as text with a CHECK constraint via
  `str_enum()` (`backend/app/models/enums.py`). Constraint name: `ck_<table>_<enum_name_in_snake_case>`.
  Adding a value needs a hand-written migration that replaces the CHECK constraint.
- Money: `Numeric(12, 2)` rupees ↔ Python `Decimal`.
- Financial year: April–March, stored as a string like `2026-27`.
- Sensitive fields (PAN, GSTIN, TAN, phone) use `EncryptedString` plus a `<field>_bidx` blind index (HMAC-SHA256)
  for uniqueness and lookups. Passwords are argon2 hashes. Uploaded files are encrypted on disk; only metadata is in the DB.
- Legal rules are **data**: every config table with thresholds, due-date rules or rates has `source_reference`,
  `effective_from`, `effective_to`. Unverified values have `TODO_VERIFY` in `source_reference` and are listed
  in `docs/TODO_VERIFY.md`.
- Constraint/index names are generated from the naming convention in `backend/app/extensions.py`.
- A module never imports another module's models; it calls that module's service functions.

## Tables

| Table | Module | One row is... | Key columns (indicative) |
|---|---|---|---|
| `users` **(implemented)** | core-auth | a login account | id, email (unique; stored trimmed + lowercased), password_hash (argon2), full_name, role (`user_role`), is_active, deleted_at, created_at, updated_at. Planned: email_verified (OTP task) |
| `email_otps` | core-auth | a one-time code | user_id, purpose (verify/reset), code_hash, expires_at, attempts, used_at |
| `notifications` | core-infra | a tray entry | user_id, type, title, body, link, read_at, created_at |
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
means telling the team (it is a contract). The **code** is what the database stores and the API sends
(lowercase snake_case, via `str_enum()`); the **label** is display text only, shown by the frontend through
`frontend/src/lib/labels.js`, which must match these tables. The migration that creates each column fixes its
CHECK constraint to exactly these codes.

**`users.role`** (core-auth; `UserRole` in `backend/app/models/enums.py`; CHECK `ck_users_user_role`)

| Code | Label | Notes |
|---|---|---|
| `business` | Business | business owner / gig worker; home `/business` |
| `ca` | Chartered Accountant | home `/ca` |
| `admin` | Admin | home `/admin` |

Also the `role` claim in the JWT.

**`compliance_items.status`** (compliance)

| Code | Label | Notes |
|---|---|---|
| `upcoming` | Upcoming | initial state |
| `docs_pending` | Docs pending | |
| `ready` | Ready | |
| `with_ca` | With CA | set from marketplace engagements |
| `filed` | Filed | |
| `filed_verified` | Filed–verified | acknowledgement verified (OCR) |
| `overdue` | Overdue | reachable from any pre-filed state |

Lifecycle: `upcoming → docs_pending → ready → with_ca → filed → filed_verified`, plus `overdue` from any pre-filed
state.

**`engagements.status`** (marketplace)

| Code | Label | Notes |
|---|---|---|
| `requested` | Requested | initial state |
| `accepted` | Accepted | |
| `quoted` | Quoted | revised quote sent (reason required) |
| `active` | Active | |
| `completed` | Completed | |
| `declined` | Declined | the CA declined the request |
| `expired` | Expired | the request auto-expired after 48 hours; the business is re-matched |

Lifecycle: `requested → accepted/quoted → active → completed`, plus `declined` / `expired`.

## Cross-module dependencies to watch
- `ca_has_active_access` (`app/utils/decorators.py`) needs engagement status from marketplace → a marketplace
  service function, not a model import.
- Compliance status "With CA" (compliance) comes from marketplace engagements (marketplace).
- Documents (documents) are attached to compliance items (compliance) and used by ca_workspace.
- CA urgency (ca_workspace) takes input from regulatory changes (regulatory) and compliance items (compliance).
