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
