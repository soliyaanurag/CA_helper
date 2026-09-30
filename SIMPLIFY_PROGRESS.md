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

## Step 2: Cross-cutting removals (done)

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

### 2.5c Matching score (done)
- Removed: POINTS_* weights, `_my_prices`, `_match_reasons`, `_ranking_key`, `_form_names`, the `user` argument of
  `list_verified_cas` and the list keys `my_prices`, `same_city`, `match_score`, `match_reasons` (and their schemas).
- Find a CA order: best rating first (unrated = 0), then most experience, then name; paginated after sorting.
- Snapshot: only the four removed keys on `/marketplace/cas` (+ the known 2.5b diffs).
- Checks: backend 604 passed; frontend 240; build OK; walk 0 failures.

### 2.5d One email switch (done)
- Table `notification_settings` (NotificationSetting) removed; new column `users.email_notifications` (default
  true). New `GET/PUT /api/v1/auth/settings` `{email_notifications}` (business and CA; admins 403, like before).
  `GET/PUT /alerts/settings` removed, with CONFIGURABLE_TYPES, ALWAYS_EMAILED_TYPES and `wants_email`.
- **Decision (plan: "It controls every notification email; code emails (OTP, password) always go out"):** the
  switch gates every email except the auth code emails and the "password changed" email: notify(email=True)
  (reminders, overdue, document requests, regulatory updates), the engagement emails (request, accepted, quoted,
  declined, expired, pro-bono match) and the CA verified/rejected emails. Before, only four types could be switched
  off and engagement/verification emails always went out. Easy to narrow if this reading is wrong.
- Snapshot: only section 4 differences (`/alerts/settings` gone, `/auth/settings` new).
- Checks: backend 604 passed; frontend 240; build OK; walk 0 failures.

### 2.5e Regulatory: no admin approval (backend done)
- `regulatory_changes.status`, `reviewed_at`, `reviewed_by_id` and RegulatoryChangeStatus removed; `notified_at` added.
- scan_news: a change Gemini extracted is sent at once (`_notify_affected`: tray + email to the affected
  businesses, tray to their active CAs, a regulatory_change_matches row each, `notified_at` set). A keyword-only
  change is saved, `notified_at` stays empty, nobody is told. `active_changes_for` no longer checks a status.
- Removed: `POST /admin/regulatory/changes/<id>/approve`, `/reject`, the `?status=` filter (now ignored),
  error CHANGE_NOT_PENDING. The CLI line says "new changes: n" (was "new changes to review").
- New `GET /api/v1/regulatory/updates` (business and CA; admin 403): the same rows as the admin list, filtered to
  the changes that name one of "your forms". **Decision:** a business's forms = the forms of its filings; a CA's
  forms = the forms of the filings in their ACTIVE engagements (the plan does not say which forms a CA has).
  Keyword-only rows are recognisable by `affected_categories.extracted_by == "keywords"` (for the page's
  "Found by keywords: read the article").
- Snapshot: only section 4 differences (new route; `?status=all` now 200 instead of 422). The demo data has no
  regulatory changes, so the row keys (`status`/`reviewed_at` out, `notified_at` in) are covered by the tests.
- Checks: backend 606 passed; frontend 240; build OK; walk 0 failures.

### 2.5f Filing page does not open the file (done)
- `compliance.get_filing` reads the acknowledgement's row (`documents_service.get_document`, the former
  `_live_document`) instead of `read_document`; verification uses the OCR fields stored at upload, as before.
- Checks: backend 607 passed; frontend 240; build OK; snapshot unchanged (99 known); walk 0 failures.

### 2.5g Config and direct emails (done)
- One `Config` class reading `os.environ` (no python-dotenv, no APP_ENV, no Development/TestingConfig).
  `create_app(test_config=None)`; the tests pass `TEST_CONFIG` (tests/conftest.py) and refuse to run when
  TEST_DATABASE_URL equals DATABASE_URL (plan step 9). APP_ENV removed from .env.example (it is harmless in an
  old .env). The dev-only fallbacks for SECRET_KEY/JWT_SECRET_KEY are gone: .env must set them (it does).
- Emails: `queue_email` and the `after_commit`/`after_rollback` listeners removed. `notify()` only adds the tray
  entry; `email_notice(user, title, body)` sends the notification email (if the switch is on) and every caller
  calls it right after its commit (document request, request fulfilled, CA marked filed, regulatory scan).
  Reminders are emailed after the job's commit.
- Checks: backend 606 passed; frontend 240; build OK; snapshot unchanged (99 known); walk 0 failures including a
  real "Scan now".

### 2.6 Files in the database (done)
- `documents.storage_key` -> `documents.content` (LargeBinary, Fernet-encrypted, deferred so lists do not load
  the files). `storage.py` keeps only `check_file` (type by first bytes + size limit; merged into utils.py in
  step 3). `UPLOAD_DIR` removed from Config, .env.example, conftest (`upload_dir` fixture) and .gitignore.
  Deleting a document deletes the file with the row.
- Local note: the old dev folder `backend/instance/uploads` (gitignored) is no longer used; left in place.
- Checks: backend 604 passed; frontend 240; build OK; snapshot unchanged (99 known); walk 0 failures.

**Step 2 done.** Backend 644 -> 604 tests (every change listed in the table below). Snapshot: 99 differences,
all section 4 (audit log, admin users `is_active`, the four ranking keys, alerts/auth settings, regulatory
routes).

### Q3 (step 2.2): permission to delete/rewrite security tests
**Answer (Anurag):** approved explicitly for the tests of the protections section 4 removes: rate limits, dummy-hash
timing, "never reveals", and later the OTP wrong-guess counter, the resend wait, soft delete, suspend/reactivate, the
audit log, the matching score, per-type email settings and regulatory approval. Everything else follows rule 5.

## Step 3: Mechanical merge (done)
- Backend app is now: `__init__.py` (Config, flask-smorest Api subclass, JWT callbacks, /api/health, BLUEPRINTS,
  create_app), `models.py` (db + every table + encryption), `utils.py` (errors, page schemas, passwords, email with
  the 13 templates as one dict, access control, GSTIN, money, file check, Gemini), `ocr.py` (ocr + document_text),
  one file per feature (`auth.py` ... `admin.py`: schemas, then logic, then routes, still flask-smorest),
  `seed.py`, `demo_seed.py`. Old packages models/, services/, routes/, schemas/, utils/, templates/ and config.py,
  extensions.py, errors.py are gone.
- Mechanical renames only: `x_service.f()` -> `x.f()`; route view functions that had the same name as their service
  function got a `_view` suffix (step 4 rewrites the routes); one local variable `documents` -> `files_by_filing`
  (ca_workspace.get_client, it hid the module). `require_ca_access` imports marketplace inside the function.
- Emails: `jinja2.Template(EMAIL_TEMPLATES[name])` (plain text like the old .txt files; `render_template_string`
  would HTML-escape). All 13 templates checked to render byte-for-byte the same as before.
- Tests: only import lines changed (aliases like `from app import compliance as compliance_service`, so bodies are
  untouched), plus test_health.py's logger name `app.routes.health` -> `app` (the module moved) and
  test_api_prefix.py imports API_PREFIX/BLUEPRINTS from `app`. eval/ scripts: imports only (aliases; step 7).
- Checks: backend 604 passed; frontend 240; build OK; snapshot unchanged (99 known); walk 0 failures; worker jobs
  listed; `flask db` works.

## Step 4: Per module, plain Flask (in progress)

### Q4 (step 4): Swagger UI / OpenAPI tests
Plain Flask routes are not in the flask-smorest OpenAPI spec, and step 5 removes flask-smorest, the OpenAPI
settings and the CI step (plan sections 1 and 6). Three tests check that part and would fail:
test_app_factory.py::test_openapi_spec_lists_health_and_every_tag, ::test_swagger_ui_is_served,
::test_api_root_redirects_to_the_docs (GET / redirects to /api/docs). Section 4 does not list them.
Validation errors: kept exactly as today (422 VALIDATION_ERROR, "Some fields are invalid.", `details` with the
invalid fields), so those 13 tests stay unchanged.
**Answer (Anurag):** delete the two Swagger/OpenAPI tests (log them under "flask-smorest removed (sections 1 and 6)");
keep GET / as a redirect, now to /api/health, and adapt that test; in step 7 remove the Swagger mentions from
README, comments and CLAUDE.md. **Standing rule:** no working feature may break; before every commit all backend
and frontend tests, `npm run build`, the snapshot compare and demo_walk.py must pass; if a feature would stop
working, stop and ask.

### 4.1 auth (done)
- Plain Flask (`bp = Blueprint("auth", ...)`, `@bp.post(...)`), plain `if` checks with the same rules and the same
  422 shape (`utils.validation_error`), `user_to_dict`. `__init__` registers plain blueprints with
  `app.register_blueprint` until step 5.
- Section 4: no password rehash, no wrong-guess counter (`email_otps.attempts` column removed), no
  one-code-per-minute wait (resend / forgot always send a new code), no `POST /auth/accept-terms`, no
  `terms_accepted` in the login response (the frontend gate only shows when it is exactly `false`, so login keeps
  working until step 6 removes the gate code). Codes still expire after 10 minutes and work once.
- Small differences from marshmallow (not features): unknown JSON fields are ignored instead of 422; the email
  format check is a simple regex; OTP_EXPIRED says "This code has expired. Ask for a new one." (no more "or was
  entered wrongly too many times").
- `utils.needs_rehash` deleted (no caller).
- Snapshot: + `terms_accepted` gone from POST /auth/login (3 roles). 102 known, 0 unexplained.
- Checks: backend 597 passed; frontend 240; build OK; walk 0 failures.

### 4.2 onboarding (done)
- Plain Flask; `read_business_form()` holds the form checks with the same rules and messages (formats, lengths,
  amount range, required-when rules, GSTIN check character/state/PAN, dropping values that do not apply);
  `business_to_dict`, `profile_to_dict`, `nic_to_dict`, `business_page`.
- Section 4: `get_threshold(key, today)` = the row with the latest `effective_from` up to today (the old
  `effective_to` check is gone; every ended rule has a successor). `compliance.sync_filings` is one short loop and
  returns `{added, removed, kept_with_ca}` (no `restored`, `moved`); the frontend "What changed" box lost those two
  lines. `resync_all_filings` returns `{businesses, added, removed}`.
- `suggest_nic_codes` returns JSON-ready dicts (shortlist as `{code, description}`); eval/nic/evaluate.py reads
  `nic["code"]` (one line).
- Until ca_workspace is converted, the four business-page schemas it inherits from (BusinessSchema,
  RegulatoryProfileSchema, NicCodeSchema, MyBusinessSchema) live in ca_workspace.py; `get_my_business` still
  returns rows for it.
- Fixed while converting: a business without a saved profile answers `profile: null` (as before), not a crash.
- demo_walk.py now also edits the business (checks the What-changed keys), asks for NIC suggestions and saves one.
- Checks: backend 597 passed; frontend 240; build OK; snapshot 102 known, 0 unexplained; walk 0 failures.

### 4.3 compliance (done)
- Plain Flask; the routes do the work (choose path, tick, mark filed, undo, acknowledgement download); the
  service functions only the routes used (`get_filing`, `choose_path`, `set_checklist_tick`, `mark_filed`,
  `unmark_filed`, `get_acknowledgement`) are gone. `filing_to_dict`, `filing_detail_to_dict`, `filing_page`.
- Section 4: peer insights is one function `peer_insights(business, filing)` with the same rule (segment = entity
  type + MSME tier with >= 10 businesses, else overall, else none) and the same JSON.
- Kept for other modules and the tests (section 7 names): `get_dashboard` (still returns the next deadline as a
  row; the route turns it into JSON), `list_filings`, `sync_filings`, `create_filings`, `checklist_*`,
  `mark_filed_by_ca`, `filings_by_acknowledgement`, `get_filings_by_ids`, `mark_filings_with_ca`,
  `list_unfiled_filings_due_by`, `business_ids_with_open_filings`, `mark_overdue_filings`, `filing_stats`,
  `form_name`, `filing_name`, `FORM_FOLDERS`, `DONE_STATUSES`, `RENAMED_FORMS`.
- Until ca_workspace is converted, the six filing schemas it inherits from live in ca_workspace.py.
- No test changed.
- Checks: backend 597 passed; frontend 240; build OK; snapshot 102 known, 0 unexplained; walk 0 failures.

### 4.4 documents (done)
- Plain Flask; the vault routes do the work (upload with optional link, list with filters + pages, download for
  the owner or an allowed CA, delete unless proof, link, unlink). `documents_to_dicts` gives the same JSON.
- `utils.read_page_args` reads ?page= / ?page_size= with the old rules and messages (used by every paged list).
- Kept for other modules: `add_document`, `get_document`, `read_document`, `remove_document`,
  `verify_acknowledgement`, `document_ids_for_filings`, `attach_document`, `documents_by_filing` (still rows,
  for ca_workspace's schema until it is converted), `GENERAL_KEY`.
- No test changed. demo_walk.py now also links, unlinks and deletes a vault document.
- Checks: backend 597 passed; frontend 240; build OK; snapshot 102 known, 0 unexplained; walk 0 failures.

### 4.5 alerts (done)
- Plain Flask; the tray routes query the user's own entries directly; `notification_to_dict`, `estimate_to_dict`.
  `flask alerts send-reminders` still works (Flask blueprint CLI group).
- Kept for other modules and the tests: `notify`, `email_notice`, `send_reminders`, `reminder_kind`,
  `_reminder_title`, `estimate_penalty` and `penalty_exposure` (still Decimals and dates; the routes convert).
- The email switch, direct emails and the nil-return fee removal were done in step 2.
- No test changed. demo_walk.py now also marks one / all notifications read and reads the penalty exposure.
- Checks: backend 597 passed; frontend 240; build OK; snapshot 102 known, 0 unexplained; walk 0 failures.

### 4.6 marketplace (done)
- Plain Flask; each route does its work (profile, certificate, Find a CA, CA page, catalog, price menu, requestable
  filings, request, quote / accept / decline / complete, accept or reject a quote, withdraw, rating, pro-bono
  page / join / cancel / queue / accept). `profile_to_dict`, `engagement_to_dict`, `rating_to_dict`,
  `pro_bono_request_to_dict`, `pro_bono_filing_to_dict`; `list_catalog` returns JSON-ready rows.
- Section 4: access checks are `ca_can_see_business(ca_profile_id, business_id)`,
  `ca_can_open_document(ca_profile_id, document_id)` and `active_filing_ids(ca_profile_id, business_id)`; callers
  updated (`utils.require_ca_access`, the documents download route). `open_engagement_item_ids` deleted (nothing
  in the app used it).
- `utils.read_uuid` (moved from documents) reads UUIDs from request values.
- Kept for other modules: `own_profile_id`, `open_filing_ids`, `active_work`, `active_cas_of_business`,
  `active_ca_users_by_filing`, `complete_if_all_filed`, `expire_old_requests`, `list_cas_for_admin`,
  `get_ca_for_admin` (still native types until admin is converted), `certificate_document_id`,
  `set_verification`, `count_cas_by_status`, `count_open_engagements`.
- Small differences from marshmallow (not features): the 422 for a wrong item inside a list names the list field
  with one message (e.g. `items`, `prices`) instead of per-index details.
- Checks: backend 597 passed; frontend 240; build OK; snapshot 102 known, 0 unexplained; walk 0 failures.

### 4.7 ca_workspace (done)
- Plain Flask; each route does its work (clients by urgency, client page, document request create / cancel,
  CA marks filed, batches, the business's requests and fulfil). `request_to_dict`. The client page reuses
  `onboarding.business_page`, `compliance.filing_detail_to_dict`, `compliance.checklist_with_ticks` and
  `documents.documents_by_filing` (now JSON-ready), so the temporary copied schemas are gone.
- `compliance.read_acknowledgement_no()` reads the optional ARN of both mark-filed forms.
- Kept for the tests: `_urgency` (native dates), `regulatory_points`, the POINTS_* weights.
- No test changed.
- Checks: backend 597 passed; frontend 240; build OK; snapshot 102 known, 0 unexplained; walk 0 failures.

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
| test_marketplace_engagements.py: test_cas_offering_my_filings_come_first_with_their_prices, test_the_match_score_adds_up_its_reasons, test_the_best_match_comes_first_not_the_most_experienced, test_a_fee_at_or_below_the_typical_fee_earns_points, test_a_good_rating_and_free_slots_earn_points (+ helpers `_reasons`, `_ca_named`) | deleted; replaced by test_the_best_rated_come_first_then_experience_then_name | marketplace: matching score removed, list order rating/experience/name |
| test_alerts_notifications.py::test_notify_respects_the_email_setting_but_always_adds_to_the_tray | renamed ..._email_switch_...; switch off via /auth/settings -> 2 tray entries, no email | alerts: one email switch |
| test_alerts_notifications.py::test_tray_and_settings_need_a_login | renamed test_the_tray_needs_a_login; the /alerts/settings case removed | alerts: notification_settings removed |
| test_alerts_notifications.py: test_settings_default_to_on_with_engagement_emails_always_sent, test_saving_settings_twice_keeps_one_row_per_type, test_engagement_emails_cannot_be_switched_off, test_admins_have_no_settings_page | replaced by test_emails_are_on_by_default, test_switching_emails_off_and_on, test_code_emails_are_sent_even_when_emails_are_off, test_settings_need_a_login, test_admins_have_no_settings_page (all on /api/v1/auth/settings) | alerts: one email switch, new /auth/settings |
| test_alerts_reminders.py::test_switched_off_emails_still_reach_the_tray | the owner's switch is off -> 2 tray entries, no email (was: one type off, overdue still emailed) | alerts: one email switch |
| test_regulatory_monitor.py::test_gemini_extracts_the_change_as_pending | renamed test_gemini_extracts_the_change; checks `notified_at` instead of status "pending" | regulatory: no admin approval |
| test_regulatory_monitor.py `pending` fixture | replaced by `found` (scan inside the test, after the business/CA exist) | regulatory: no admin approval |
| test_regulatory_monitor.py::test_admin_sees_pending_changes_with_their_article | renamed ..._sees_the_changes_...; no `?status=` | regulatory: no admin approval |
| test_regulatory_monitor.py::test_approval_tells_the_business_and_its_ca | rewritten as test_a_change_from_gemini_tells_the_business_and_its_ca_at_once | regulatory: auto-notify |
| test_regulatory_monitor.py::test_approval_raises_the_clients_urgency, test_old_changes_no_longer_raise_urgency | renamed/cleaned: no approve call (the scan notifies) | regulatory: auto-notify |
| test_regulatory_monitor.py::test_a_change_for_another_scheme_or_state_tells_nobody, test_a_filed_filing_is_not_affected | scan after the setup instead of approving | regulatory: auto-notify |
| test_regulatory_monitor.py::test_rejection_tells_nobody_and_a_change_is_reviewed_once | replaced by test_a_change_found_by_keywords_tells_nobody | regulatory: no approval; keyword-only finds only listed |
| test_regulatory_monitor.py (new) test_updates_show_the_changes_about_my_forms, test_updates_are_for_businesses_and_cas | added | regulatory: new GET /regulatory/updates |
| test_regulatory_monitor.py::test_scan_command | expects "new changes: 1" (was "new changes to review: 1") | regulatory: no admin approval |
| test_compliance_filing_page.py (new) test_the_filing_page_does_not_open_the_acknowledgement_file | added | compliance: the page shows the acknowledgement without opening the file |
| conftest.py `app` fixture, test_app_factory.py::test_unhandled_error_returns_standard_500_error | `create_app(TEST_CONFIG)` instead of `create_app("testing")` | Cross-cutting: one Config class, tests override values in conftest.py |
| test_alerts_notifications.py::test_notify_emails_only_after_the_commit | rewritten as test_email_notice_emails_the_tray_text | Cross-cutting: emails sent directly, no queue |
| test_alerts_notifications.py::test_a_rolled_back_notification_sends_no_email | deleted (no queue to drop) | Cross-cutting: emails sent directly, no after_commit listener |
| test_alerts_notifications.py::test_notify_respects_the_email_switch_but_always_adds_to_the_tray | uses notify() + email_notice() | Cross-cutting: emails sent directly |
| test_storage.py::test_a_file_is_stored_encrypted_and_read_back, test_a_key_is_never_a_path | deleted (no files on disk, no storage keys); the type/size tests call `check_file` | documents: files stored in documents.content |
| test_documents_vault.py::test_the_owner_downloads_the_decrypted_file | checks `documents.content` is encrypted instead of the file on disk | documents: files stored in documents.content |
| test_marketplace_engagements.py `_add_document` helper | `content=encrypt_bytes(...)` instead of a storage key | documents: files stored in documents.content |
| conftest.py `upload_dir` fixture | deleted | documents: UPLOAD_DIR and the upload folder go |
| test_auth_verify_email.py::test_a_wrong_code_is_refused_and_counted | renamed test_a_wrong_code_is_refused; the `attempts == 1` check removed | auth: wrong-guess counter removed |
| test_auth_verify_email.py::test_the_code_stops_working_after_too_many_wrong_guesses | deleted | auth: wrong-guess counter removed |
| test_auth_verify_email.py::test_resend_sends_at_most_one_code_a_minute | rewritten as test_resend_sends_a_new_code_right_away | auth: one-code-per-minute wait removed |
| test_auth_password_reset.py::test_forgot_password_sends_at_most_one_code_a_minute | rewritten as test_forgot_password_sends_a_new_code_each_time | auth: one-code-per-minute wait removed |
| test_auth_login.py::test_outdated_hash_is_rehashed_on_login | deleted | auth: password rehash removed |
| test_auth_login.py::test_login_says_whether_the_terms_were_accepted, test_accept_terms_records_consent_once | deleted | auth: accept-terms endpoint and consent gate removed |
| test_app_factory.py::test_openapi_spec_lists_health_and_every_tag, test_swagger_ui_is_served | deleted | flask-smorest removed (sections 1 and 6), Q4 |
| test_auth_me_and_permissions.py::test_openapi_marks_login_and_health_public_and_the_rest_protected (+ its PUBLIC_AUTH_PATHS list) | deleted. **Flag:** a third OpenAPI test Q4 did not name; same reason (nothing uses /api/openapi.json) | flask-smorest removed (sections 1 and 6), Q4 |
| test_compliance_items.py::test_an_audit_moves_the_itr_due_date | the `counts["moved"] == 1` check removed (the due date check stays) | onboarding: "What changed" counts without `moved` |
| test_onboarding_edit.py::test_switching_to_monthly_returns_changes_the_profile_and_filings, test_switching_back_to_quarterly_removes_the_extra_months | the `moved` checks removed (added/removed and the labels are still checked) | onboarding: "What changed" counts without `moved` |
| test_compliance_legal_update.py::test_resync_reports_what_moved | renamed test_resync_moves_the_due_date_back_to_the_rule; checks the ITR due date instead of `counts["moved"]` | onboarding: sync counts without `moved` |
| frontend OnboardingPage.test.jsx (edit test fixture) | `filings` without `restored`/`moved` | onboarding: update the frontend "What changed" box |
| test_marketplace_engagements.py (access-check tests) | `ca_has_active_access` -> `ca_can_see_business`, `ca_can_access_document` -> `ca_can_open_document`, `active_engagement_item_ids` -> `active_filing_ids` | marketplace: access checks are two plain functions plus active_filing_ids |
| test_marketplace_engagements.py::test_open_items_cover_requests_but_not_ended_ones | rewritten as test_requested_filings_are_not_active_work (the `open_engagement_item_ids` checks removed) | marketplace: access checks are two plain functions plus active_filing_ids |
