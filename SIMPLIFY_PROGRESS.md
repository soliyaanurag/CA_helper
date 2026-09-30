# Simplification progress

Log of the run that follows `SIMPLIFICATION_PLAN.md`. Re-read both files before each step.

**Standing rule from Anurag (30 Sep 2026):** do not disrupt current functionality except where the plan
(section 4) or the prompt explicitly says so.

How to check after every step:
- backend tests, frontend tests, `npm run build`
- `python api_snapshot.py --compare` (repo root; after step 1 inside the backend container:
  `docker compose exec backend python ../api_snapshot.py --compare`). It uses its own database
  `ca_helper_snapshot` on the same server, so it never touches the dev data.

## Answered questions

### Q1 (step 0): which main to start from?
PRs #35 (legal update) and #34 (FAQ pages + assistant eval) were open. **Answer:** Anurag merged both first;
the tag and branch were made after that.

## Step 0: baseline (done)
- main at `5add203` (after merging #35 and #34). Tagged `before-simplify` and pushed the tag. Branch `simplify`.
- Old tooling on main: `make test` = **644 backend tests passed, 240 frontend tests passed (36 files)**;
  `npm run build` OK.
- `api_snapshot.py` written. It builds a fresh `ca_helper_snapshot` database (`db.create_all()`, like the tests),
  runs `seed-demo` through the Flask CLI, logs in as the demo business, CA and admin, then calls:
  every GET route without ids as each role and anonymously; the list endpoints with the filters the frontend sends;
  every GET route with ids, the ids taken from list responses (up to 40 each); a few 404 cases.
  It records status codes, content type and, per JSON path, the value types (string / number / bool / null /
  list / object, plus money = `"1250.00"`, date, datetime, uuid). It finds `db` via `app.extensions["sqlalchemy"]`
  and the seed via the `seed-demo` command, so it works unchanged through the refactor.
- Baseline `api_snapshot_baseline.json`: 184 endpoint entries, every GET route called. A second run: no differences.
- Known gaps of the snapshot (the tests cover these): the demo data has no regulatory changes and no assistant
  history, so those list shapes are empty lists; POST responses are not recorded (except login).

## Step 1: Docker Compose, delete tooling (done)

### Q2 (step 1): the npm packages behind the deleted config files
The plan deletes `eslint.config.js`, `.prettierrc.json`, `.prettierignore` and `components.json`, but does not name the
npm packages that only they use (`eslint`, `@eslint/js`, `eslint-config-prettier`, `eslint-plugin-react-hooks`,
`eslint-plugin-react-refresh`, `globals`, `prettier`, `prettier-plugin-tailwindcss`, `shadcn`) or the `lint`,
`format`, `format:check` npm scripts, which would fail without their configs.
**Answer:** remove the 8 lint/format packages and the `lint`, `format`, `format:check` scripts; keep `shadcn`
(`src/index.css` imports `shadcn/tailwind.css`).

Done:
- `docker-compose.yml` exactly as plan section 9 (db without a host port, Mailpit, backend, worker with profile,
  frontend). `main.py` listens on 0.0.0.0; Vite proxies `/api` to `API_URL` or `http://127.0.0.1:8000`.
- Deleted: Makefile, scripts/, environment.yml, .vscode/, .editorconfig, .gitattributes, ruff.toml,
  backend/requirements-dev.txt (pytest moved into requirements.txt, ruff dropped), frontend .prettierrc.json,
  .prettierignore, eslint.config.js, components.json, jsconfig.json, .npmrc. npm: the 8 lint/format packages and
  scripts removed (Q2).
- CI installs `backend/requirements.txt`; ruff, ESLint and Prettier steps removed (migrations and OpenAPI steps
  stay until steps 2 and 5).
- `.env.example`: DATABASE_URL points at the `db` container, POSTGRES_*/DB_HOST_PORT/TEST_DATABASE_URL/MAIL_SERVER
  removed (compose sets them), secret placeholders with how to generate them. `.gitignore`: conda link and
  .vscode exceptions removed.
- CLAUDE.md moved to docs/old-CLAUDE.md; new CLAUDE.md = plan section 8 word for word.
- Local machine: the old `make infra` containers (project `ca-helper`) were stopped; their volume
  `ca-helper_pgdata` is kept (not deleted). The new stack uses a new volume `ca_helper_pgdata`.
  In `.env`, the host of DATABASE_URL was changed from localhost to `db` (nothing else in .env was changed).

Checks (all inside the containers):
- `docker compose up -d`: db, mailpit, backend, frontend up; `flask db upgrade` + `flask seed-demo` OK;
  /api/health OK directly and through the Vite proxy.
- backend 644 passed; frontend 240 passed (36 files); `npm run build` OK.
- Snapshot compare: no differences.
- Tests changed: none.

## Step 2: Cross-cutting removals (in progress)

### 2.1 Migrations (done, commit ba2ecae)
- `backend/migrations/versions/*` deleted; `flask reset-db` added (asks for confirmation; drops the `public` schema,
  creates the vector extension and every table from the models, runs the seed). CI "Migrations apply cleanly"
  step removed. Backend 644 passed.

### 2.2 Rate limiting, row locking, anti-enumeration (done)
- Flask-Limiter removed (requirements, extensions, config, every `@limiter.limit`, the conftest reset fixture).
- `with_for_update` removed: `compliance.get_filings_by_ids(ids)` has no `lock` argument now; accepting a pro-bono
  request no longer locks the row.
- Login no longer checks a dummy hash for an unknown email (same 401 INVALID_CREDENTIALS).
- resend-code and forgot-password: unknown email -> 404 USER_NOT_FOUND; resend for a verified email -> 409
  EMAIL_ALREADY_VERIFIED (existing codes). The frontend pages already show the server's message; no change needed.
- Checks: backend 637 passed; frontend 240 passed; build OK; snapshot no differences; demo walk 0 failures.

### 2.3 Soft delete -> real delete (done)
- `SoftDeleteMixin` removed. `users.is_active` stays until suspend goes (2.5); `users.deleted_at` is gone.
- Partial unique indexes -> plain UNIQUE: `businesses.user_id` (`uq_businesses_user_id`) and
  (business_id, form_code, period_start) on compliance_items (`uq_compliance_items_business_id`).
- Real deletes: a filing that no longer applies (with its checklist ticks, document links, reminder log rows,
  document requests and engagement items of closed engagements; its files stay in the vault); a document (its links,
  its row and its encrypted file; a document request it answered keeps status fulfilled with document_id NULL);
  the old CA certificate on re-upload; a CA price row left out of the menu; chat history on "clear".
- All `deleted_at`/`is_active` filters on businesses, filings, documents, notifications, CA profiles, catalog,
  CA prices and chat messages removed.
- `sync_filings` still returns the `restored` key (always 0) and `moved`; they go in step 4 onboarding together with
  the frontend "What changed" box (step 6).
- Checks: backend 629 passed; frontend 240 passed; build OK; snapshot no differences; demo walk 0 failures.
  Dev database recreated with `flask reset-db` + `flask seed-demo`.

### 2.4 Enums -> String columns (done)
- Every `str_enum(...)` column is now `String(50)` (`Mapped[str]`); the StrEnums stay next to their models and the
  request schemas check them (`fields.String(validate=validate.OneOf(list(X)))` instead of `fields.Enum`).
- Removed: `str_enum()`, `only_codes()` and every generated CHECK (enum values and the code-list checks on
  `ca_profiles.languages/specializations` and `regulatory_changes.form_codes`).
- Kept (hand-written, a reader expects them; section 4 does not list them): amounts/prices >= 0, stars 1-5,
  GSTIN when GST registered, TAN when deducting TDS, CIN/LLPIN for LLPs and companies, valid rule periods, fy
  format, quote needs a reason, checklist key not empty. **Unsure:** the plan says "the few CHECKs a reader
  expects"; I kept these because removing them would change what the database accepts beyond section 4.
- Loaded values are plain `str` now, so `.value` on a loaded column was removed (JWT role claim, counts, profile
  facts, admin rows, regulatory change rows). StrEnum members still compare and hash equal to their values.
- Checks: backend 622 passed; frontend 240 passed; build OK; snapshot no differences; demo walk 0 failures.

### 2.5a Unused schema (done)
- Tables `client_invites` (ClientInvite, InviteStatus) and `ca_notes` (CaNote) removed; nothing used them.
- `compliance_items.is_nil_return` and `penalty_rules.nil_return_late_fee_per_day` removed, with the nil-return
  branch of the late fee and the three seeded "20" values (the source texts that cite them are unchanged).
- Checks: backend 621 passed; frontend 240; build OK; snapshot no differences; walk 0 failures.

### 2.5b Suspend/reactivate and the audit log (done)
- Removed: `users.is_active`, table `admin_audit_log` (models/admin.py), `POST /admin/users/<id>/suspend`,
  `/reactivate`, `GET /admin/audit-log`, their schemas, `auth_service.get_user_for_admin/set_user_active/names_of`,
  `marketplace_service.cancel_open_requests_of_ca` and `ca_names`, login's 403 ACCOUNT_INACTIVE, the
  `is_active` checks in reminders, notifications and the CA list.
- `auth_service.get_active_user` -> `get_user(user_id)`; the JWT loader still answers 401 ACCOUNT_INACTIVE (existing
  code) for a token whose user no longer exists.
- The frontend still has the suspend buttons and the audit log page until step 6.
- Snapshot: only section 4 differences: `/admin/audit-log` gone (404), `is_active` gone from `/admin/users` items.
- Checks: backend 608 passed; frontend 240; build OK; walk 0 failures.

### Q3 (step 2.2): permission to delete/rewrite security tests
**Answer (Anurag):** approved explicitly for the tests of the protections section 4 removes: rate limits, dummy-hash
timing, "never reveals", and later the OTP wrong-guess counter, the resend wait, soft delete, suspend/reactivate, the
audit log, the matching score, per-type email settings and regulatory approval. Everything else follows rule 5.

## Changed or deleted tests (with their section 4 item)

| Test | Change | Section 4 item |
|---|---|---|
| conftest.py `_reset_rate_limits` fixture | deleted | Cross-cutting: rate limiting removed |
| test_auth_change_password.py::test_change_password_is_rate_limited_to_10_per_minute | deleted | Cross-cutting: rate limiting removed |
| test_auth_login.py::test_login_is_rate_limited_to_10_per_minute | deleted | Cross-cutting: rate limiting removed |
| test_auth_password_reset.py::test_forgot_password_is_rate_limited_to_3_per_minute | deleted | Cross-cutting: rate limiting removed |
| test_auth_signup.py::test_signup_is_rate_limited_to_5_per_minute | deleted | Cross-cutting: rate limiting removed |
| test_auth_verify_email.py::test_resend_is_rate_limited_to_3_per_minute | deleted | Cross-cutting: rate limiting removed |
| test_onboarding_nic.py::test_suggestions_are_rate_limited | deleted | Cross-cutting: rate limiting removed |
| test_auth_login.py::test_unknown_email_still_checks_a_password_hash | deleted | auth: dummy-hash timing trick removed |
| test_auth_password_reset.py::test_forgot_password_never_reveals_whether_an_account_exists | rewritten as test_forgot_password_for_an_unknown_email_is_404 (404 USER_NOT_FOUND) | auth: "always 204" answers removed |
| test_auth_verify_email.py::test_resend_never_reveals_whether_an_account_exists | rewritten as test_resend_for_an_unknown_or_verified_email_is_an_error (404 USER_NOT_FOUND / 409 EMAIL_ALREADY_VERIFIED) | auth: "always 204" answers removed |
| test_db_foundations.py::test_soft_delete_mixin_defaults_to_active | deleted | Cross-cutting: soft delete removed |
| test_db_foundations.py::test_database_defaults_cover_raw_sql_inserts | no longer reads `is_active` (timestamps only) | Cross-cutting: soft delete removed |
| tests/_models.py `Gadget` | no SoftDeleteMixin | Cross-cutting: soft delete removed |
| test_compliance_items.py `by_key` helper | no `deleted_at` filter | Cross-cutting: soft delete removed |
| test_compliance_items.py::test_a_filing_that_no_longer_applies_is_soft_deleted | renamed ..._is_deleted; asserts the rows are gone | Cross-cutting: soft delete removed |
| test_compliance_items.py::test_a_filing_that_applies_again_is_reactivated_not_inserted | renamed ..._is_added_again; asserts added == 4 | Cross-cutting: soft delete removed; onboarding: no `restored` |
| test_onboarding_edit.py `live_forms`, labels filter, ..._keeps_filings_in_an_open_engagement | no `deleted_at`; the kept filing still exists | Cross-cutting: soft delete removed |
| test_compliance_overdue.py::test_removed_filings_are_left_alone | deleted (no soft-deleted filings exist) | Cross-cutting: soft delete removed |
| test_documents_vault.py::test_delete_is_soft_and_removes_open_links | renamed test_delete_removes_the_document_and_its_links; the row is gone | documents: delete is a real delete |
| test_documents_vault.py::test_proof_of_a_filed_filing_cannot_be_deleted | checks the row still exists instead of `deleted_at is None` | documents: delete is a real delete |
| test_admin_ca_verification.py::test_a_new_certificate_sends_a_verified_ca_back_to_pending | counts all documents (old certificate deleted) | Cross-cutting: soft delete removed |
| test_alerts_notifications.py::test_the_tray_shows_only_own_live_entries | renamed ..._own_entries; the "dismissed" entry is deleted instead of soft-deleted | Cross-cutting: soft delete removed |
| test_assistant.py::test_history_is_saved_listed_and_cleared | cleared messages are deleted (count 0, was 2) | Cross-cutting: soft delete removed |
| test_auth_login.py::test_soft_deleted_user_is_rejected | deleted | Cross-cutting: soft delete removed |
| test_marketplace_ca_list.py::test_lists_only_verified_cas_with_live_accounts | "Deleted CA" case removed | Cross-cutting: soft delete removed |
| test_marketplace_ca_detail.py `service` fixture, ..._in_catalog_order_with_ranges | no `is_active`; a dropped price row is deleted | Cross-cutting: soft delete removed |
| test_marketplace_ca_detail.py::test_hides_services_removed_from_the_catalog | deleted (a catalog service cannot be soft-deleted any more) | Cross-cutting: soft delete removed |
| test_marketplace_ca_detail.py::test_unlisted_cas_are_not_found[deleted] | parameter removed | Cross-cutting: soft delete removed |
| test_marketplace_services.py `catalog` fixture | "retired" (inactive) service removed | Cross-cutting: soft delete removed |
| test_marketplace_services.py::test_only_active_catalog_services_can_be_priced[retired/made_up] | now test_only_catalog_services_can_be_priced (unknown id only) | Cross-cutting: soft delete removed |
| test_marketplace_services.py::test_range_counts_only_listed_cas_and_current_prices | deleted-user case removed; the dropped price row is deleted | Cross-cutting: soft delete removed |
| test_marketplace_services.py::test_saving_again_replaces_the_menu | a dropped price row is deleted and re-offering adds a new row | Cross-cutting: soft delete removed |
| test_schema_constraints.py::test_a_user_has_at_most_one_live_business, ..._one_live_filing_... | renamed without "live"; new constraint names | Cross-cutting: partial indexes -> UNIQUE |
| test_schema_constraints.py::test_a_soft_deleted_business_does_not_block_a_new_one | deleted | Cross-cutting: soft delete removed |
| test_schema_constraints.py::test_a_soft_deleted_filing_can_be_created_again | deleted | Cross-cutting: soft delete removed |
| test_db_foundations.py::test_enum_stores_the_value_and_loads_the_member | renamed test_enum_stores_the_value; compares with == (a plain str loads back) | Cross-cutting: enums -> String columns |
| test_db_foundations.py::test_enum_rejects_unknown_value_in_the_orm, ..._check_constraint_rejects_unknown_value_in_raw_sql, ..._check_constraint_has_a_stable_name, ..._values_must_be_lowercase_snake_case, ..._constraint_name_can_be_overridden | deleted (tested `str_enum()` and its generated CHECK) | Cross-cutting: enums -> String, no generated CHECKs |
| tests/_models.py `Gadget.colour` | String(50) instead of str_enum | Cross-cutting: enums -> String columns |
| test_marketplace_ca_profile.py::test_database_rejects_unknown_codes | deleted (generated code-list CHECK) | Cross-cutting: no generated CHECKs |
| test_schema_constraints.py::test_an_unknown_enum_value_is_refused_even_in_raw_sql | deleted (generated enum CHECK) | Cross-cutting: no generated CHECKs |
| test_regulatory_monitor.py (5 asserts) | `x.value == "..."` -> `x == "..."` (loaded values are str) | Cross-cutting: enums -> String columns |
| test_alerts_penalties.py::test_a_nil_return_uses_its_own_daily_fee | deleted | Cross-cutting: `is_nil_return` and the nil-return fee removed |
| test_admin_users.py: test_a_suspended_user_cannot_log_in_or_use_a_token, test_reactivate_lets_them_log_in_again, test_suspend_checks, test_suspending_twice_is_refused, test_a_suspended_ca_leaves_the_marketplace_and_open_requests_are_cancelled, test_only_admins_suspend[2], test_audit_log_lists_actions_newest_first, test_audit_log_is_for_admins | deleted (the file keeps the two AD5 filing-stats tests) | admin: suspend, reactivate, audit log removed |
| test_admin_ca_verification.py::test_an_admin_verifies_a_ca_who_is_emailed_and_logged | renamed ..._is_emailed; the audit-log assertion removed | admin: audit log removed |
| test_alerts_reminders.py::test_a_deactivated_owner_gets_nothing | deleted | admin: suspend removed |
| test_auth_login.py::test_inactive_user_is_rejected, test_inactive_user_with_wrong_password_gets_invalid_credentials | deleted | admin: suspend removed |
| test_auth_me_and_permissions.py::test_token_of_deactivated_user_is_401 | rewritten as test_token_of_a_user_that_no_longer_exists_is_401 (same 401 ACCOUNT_INACTIVE) | admin: suspend removed |
| test_auth_password_reset.py::test_forgot_password_for_an_unknown_email_is_404 | the suspended-account case removed | admin: suspend removed |
| test_marketplace_ca_list.py::test_lists_only_verified_cas_with_live_accounts | renamed test_lists_only_verified_cas; deactivated case removed | admin: suspend removed |
| test_marketplace_ca_detail.py::test_unlisted_cas_are_not_found[deactivated] | parameter removed | admin: suspend removed |
| test_marketplace_services.py::test_range_counts_only_listed_cas_and_current_prices | deactivated-user case removed | admin: suspend removed |
