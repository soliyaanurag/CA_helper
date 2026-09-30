# CA Helper — simplification plan

Goal: the same product, written like a clean beginner-level university project. Every file should be
something one of us can open in the viva and explain line by line. Behaviour stays the same except for
the changes listed in **section 4** (and only those).

Put this file in the repo root while the work is going on. It is executed by **one Claude Code run** using the prompt
in section 11, which works through the steps in order and records its progress in `SIMPLIFY_PROGRESS.md`, so a new
session can continue where the last one stopped.

---

## 1. Decisions (agreed 30 Sep 2026)

| Topic | Decision |
|---|---|
| Database | **Neon** (shared by the team) for the app. A Postgres container only for running tests. |
| Running the app | One `docker-compose.yml`: frontend, backend, worker, Mailpit, test database. No Makefile, no scripts, no conda. |
| Backend style | **Plain Flask** (`@bp.get/post`, `request.get_json()`, `jsonify`). flask-smorest and marshmallow go. Nothing in the frontend depends on them (checked: the frontend never reads validation `details`). |
| Frontend | **Keep the libraries** (React Query, React Hook Form + Zod, shadcn/Tailwind). Fewer files, simpler code. |
| Legal rules | **Keep the 3 tables** (`rule_thresholds`, `obligation_templates`, `penalty_rules`), simpler code that reads them. |
| Encryption | **Keep, simplified**: PAN/GSTIN/TAN/phone and uploaded files, one shared key for the team. |
| Files | Stored **in the database** (encrypted bytes), not on disk. Required for Neon. |
| Migrations | Deleted during the work; **one fresh migration** at the end. |
| Tests | **Keep all test files** (updated as the code changes). They are the safety net. Remove before the viva if you want. |
| Docs | `docs/` kept as it is (nothing in the code reads it). Only `CLAUDE.md` is replaced (section 8), because it instructs Claude Code. |
| Removed | Admin audit log, suspend/reactivate, the matching score ("why this CA"), per-type email settings, rate limiting, anti-enumeration tricks, row locking, soft delete, unused tables. |
| Changed | Regulatory news: no admin approval. AI-read changes notify users directly; keyword-only finds are only listed. One email on/off switch per user. |
| Kept | Everything else, including OTP email (Mailpit), quotes + 48 h expiry, pro-bono, doc requests, batches, peer insights, penalties, all OCR, NIC suggestion, AI assistant with fallbacks. |

---

## 2. What "simple, human-written code" means here

This is the style every changed file must follow. It matters more than the line count.

**Do**
- Plain functions and `for` loops. One route = one function that reads the input, does the work, commits and returns JSON.
- Names a student would pick: `get_filing`, `send_reminders`, `ca_can_see_business`.
- Short docstrings (one line) and comments only where the *why* is not obvious. Normal sentences, no rule numbers.
- Commit in the route (`db.session.commit()`) right before returning.
- `if` checks that return an error: `raise ApiError(404, "FILING_NOT_FOUND", "Filing not found.")`.
- Keep the existing **error codes** (the frontend and the tests use them). Just don't invent new ones.
- Magic numbers as a named constant at the top of the file (`REMINDER_DAYS = [7, 3, 1]`).

**Don't**
- No task IDs (`CO10`, `MA8`, `AS2`), no "(rule 3)", no "see docs/DECISIONS.md" in code or comments.
- No module docstrings that list every function. No "Does not commit." notes on every helper.
- No decorators-inside-decorators, no `functools.cache`, no SQLAlchemy event listeners, no `**{...}` merges.
- No helper written for one caller, no code for cases that "might happen one day".
- No fallback chains more than one level deep. One `try/except` around a Gemini call, one fallback.
- No type hints on everything (keep them only where they help, e.g. model columns).

**Example: before (4 files) and after (1 function)**

Before: a `MethodView` class with `@blp.arguments(ChoosePathSchema)` / `@blp.response(200, FilingPageSchema)` in
`routes/compliance.py`, a schema class in `schemas/compliance.py`, a service function in
`services/compliance_service.py` with a 5-line docstring.

After, in `app/compliance.py`:

```python
@bp.post("/compliance/items/<uuid:item_id>/path")
@login_required("business")
def choose_path(item_id):
    path = request.get_json().get("path")
    if path not in ("self", "ca"):
        raise ApiError(422, "VALIDATION_ERROR", "Choose 'self' or 'ca'.")
    filing = get_own_filing(item_id)
    if filing.status not in NOT_STARTED:
        raise ApiError(409, "FILING_LOCKED", "This filing is already with a CA or filed.")
    filing.filing_path = path
    db.session.commit()
    return jsonify(filing_page(filing))
```

**The JSON contract does not change.** Same URLs, same keys, money as a string with 2 decimals (`"1250.00"`), dates as
`"YYYY-MM-DD"`, timestamps as ISO strings, ids as strings, enum values as the same lowercase codes. The frontend is not
rewritten, so every response must look exactly like today's.

---

## 3. Target structure

### Repo root
```
docker-compose.yml   .env.example   .gitignore   README.md   CLAUDE.md (new, short)
SIMPLIFICATION_PLAN.md (delete at the end)
.github/workflows/ci.yml   content/   eval/   docs/ (unchanged)
```
Deleted: `Makefile`, `scripts/`, `environment.yml`, `.vscode/`, `.editorconfig`, `.gitattributes`, `ruff.toml`,
`backend/requirements-dev.txt` (pytest goes into `requirements.txt`; `backend/pyproject.toml` stays, it only holds
3 pytest settings), frontend `.prettierrc.json`, `.prettierignore`,
`eslint.config.js`, `components.json`, `jsconfig.json`, `.npmrc`.

### Backend (67 Python files → about 17)
```
backend/
  requirements.txt       (one file; dev packages = pytest only)
  main.py                dev server on 0.0.0.0:8000
  worker.py              the 4 scheduled jobs
  app/
    __init__.py          create_app(): config from env, db, jwt, blueprints, CLI commands
    models.py            every table + EncryptedString + encrypt/decrypt helpers
    utils.py             ApiError + handler, login_required(role), current_user/current_business,
                         send_email (templates as strings in one dict), notify(), Gemini (scrub_pii,
                         ask_gemini, embed_texts), GSTIN checks, format_inr, file type/size check
    ocr.py               extract_text + reading fields from the text (today ocr.py + document_text.py)
    auth.py  onboarding.py  compliance.py  documents.py  marketplace.py
    ca_workspace.py  alerts.py  regulatory.py  assistant.py  admin.py
                         each = its blueprint, routes, validation, logic, to_dict helpers
    seed.py  demo_seed.py
  migrations/            one file, generated in step 8
  tests/                 kept (imports updated)
```
Dependency direction (no import loops): `models.py` ← `utils.py` ← feature files. A feature file that needs another
feature imports the **module** (`from app import compliance`) and calls `compliance.list_filings(...)` inside
functions, as today.

### Frontend (79 source files → about 25)
```
frontend/src/
  main.jsx               entry, QueryClient, router
  routes.jsx             routes + NAV + AppShell + RequireRole + PublicLayout
  auth.jsx               AuthProvider + useAuth (today context/ + hooks/)
  api.js                 apiFetch + every hook (today 12 files in api/)
  lib.js                 labels, money, dates, gstin, session, authRules, cn (today 8 files in lib/)
  components/ui.jsx      button, card, input, label, badge (today 5 shadcn files)
  components/shared.jsx  FormField, FormCard, StatusBadge, Stars, Markdown, EngagementCard, NotificationBell
  components/assistant.jsx  AssistantChat + AssistantWidget (the full page reuses it)
  pages/AuthPages.jsx    Home, Login, Signup, VerifyEmail, ForgotPassword, ResetPassword, ChangePassword, Terms, NotFound
  pages/SettingsPage.jsx one "email me" switch, business and CA
  pages/business/        Dashboard, Onboarding (+NicCodeCard), Calendar, Filing, Documents,
                         FindCa (list + CA page + request + typical fees), Engagements (+ pro-bono),
                         RegulatoryUpdates (new)
  pages/ca/              Dashboard, Profile (+ services & prices), Engagements (+ pro-bono queue),
                         Clients (list + client page + batches)
  pages/admin/           AdminPages.jsx (dashboard, users, CA detail, regulatory)
  test/                  unchanged helpers; *.test.jsx files kept, imports updated
```

---

## 4. What changes in each module (the only intended behaviour changes)

Anything not listed here must keep working exactly as today. A test may only be changed or deleted if it tests an
item in this section. Everything else in the test suite must pass unchanged, apart from import paths.

### Cross-cutting (step 2)
- **Soft delete removed everywhere.** `is_active`/`deleted_at` columns and the partial unique indexes go; they become
  plain `UNIQUE`. Removing something deletes the row (and its child rows first). Filings that no longer apply after a
  profile edit are deleted, unless they are filed, with a CA or in an open engagement.
- **Enums** become plain `String` columns. The allowed values stay as Python constants/`StrEnum`s next to the model
  and are checked in the code. No generated CHECK constraints. Keep: NOT NULL, UNIQUE, foreign keys, and the few
  CHECKs a reader expects (stars 1–5, amounts ≥ 0).
- **Rate limiting removed** (Flask-Limiter uninstalled; 429 no longer happens).
- **Row locking removed** (`with_for_update()` calls).
- **Unused schema removed:** `client_invites`, `ca_notes` tables; `compliance_items.is_nil_return` (and the nil-return
  fee); `users.is_active` goes together with suspend.
- **Config:** one `Config` class reading environment variables (Docker Compose loads `.env`); tests override values
  in `conftest.py`. `python-dotenv` removed.
- **Emails** are sent directly (no queue on the session, no `after_commit` listener). Call `send_email` after the commit.

### auth
- Keep: signup with emailed 6-digit code (Mailpit), verify, resend, login, forgot/reset password, change password,
  terms checkbox at signup, JWT, role check.
- Remove: dummy-hash timing trick, password rehash, wrong-guess counter, one-code-per-minute wait, "always 204" answers
  (unknown email now gets a normal 404), the `accept-terms` endpoint and the one-time consent gate (no old accounts
  exist after the fresh database).
- Keep: code expires after 10 minutes and works once.

### onboarding
- Keep: registration form and checks (PAN/GSTIN/TAN formats, GSTIN check digit + state + PAN), profile engine with a
  "why" per line reading `rule_thresholds`, NIC suggestion (keyword shortlist → Gemini picks, keyword fallback), OCR
  auto-fill, edit + "What changed".
- Simplify: after an edit, filings are synced in one short function (add missing, delete ones that no longer apply
  unless kept, update due dates of not-started ones). "What changed" returns the profile lines that changed and
  `{added, removed, kept_with_ca}` counts (no `restored`, `moved`; update the frontend box).
- `_threshold()` becomes one small `get_threshold(key)` query (latest `effective_from` ≤ today).

### compliance
- Keep: templates + due-date rules, filings per FY, calendar list and filters, filing page, checklist ticks → status,
  choose path, mark filed / undo, overdue job, dashboard numbers, peer insights, admin filing stats.
- Fix: the filing page shows the acknowledgement's name and verification **without opening the file** (today it
  decrypts the file on every page view, which also breaks on Neon if the file is missing).
- Peer insights: same rule (segment = entity type + MSME tier, shown with ≥ 10 businesses, else overall), in one
  short function.

### documents
- Files stored in `documents.content` (encrypted bytes, `LargeBinary`). `storage.py`, `UPLOAD_DIR` and the upload
  folder go. Type check by first bytes and the size limit stay.
- Keep: upload, list with filters, download (owner, or CA with an active engagement), delete (refused for proof of a
  filed filing), link to checklist entry (ticks it), unlink, all OCR (filed-verified check, type warning).
- Delete is a real delete (row + links).

### alerts
- Keep: tray + bell + mark read, daily reminders (T-7/T-3/T-1/overdue, once each, not for filings due before the
  business registered, one summary email), penalty estimate + dashboard exposure with the "pending verification"
  label.
- Change: `notification_settings` table removed; new column `users.email_notifications` (default true). One switch on
  the new Settings page. It controls every notification email; code emails (OTP, password) always go out.
- Penalty: flat fee, or days × daily fee capped at the maximum; interest when tax due is typed. Nil-return fee removed.

### marketplace
- Keep: CA profile + certificate upload + verification status, service catalog and CA prices, typical range (median,
  3+ CAs), Find a CA **with its filters** (service, specialization, language, city) and the service price, CA page,
  request → accept / quote → accept or reject quote / decline / withdraw → active → completed, 48 h expiry job,
  capacity limit, ratings, pro-bono queue with monthly slots, the access-check functions.
- Remove: matching score, `match_reasons`, `my_prices`, `same_city` and the ranking. List order: rating, then
  experience, then name.
- Access checks are two plain functions: `ca_can_see_business(ca, business_id)` and
  `ca_can_open_document(ca, document_id)`, plus `active_filing_ids(ca, business_id)`.
- Remove `cancel_open_requests_of_ca` (only used by suspend).

### ca_workspace
- Keep everything (clients + urgency with reasons, client page, document requests, CA marks filed, batches), in
  simpler code.

### regulatory
- Keep: sources (RSS + web page), robots.txt check, daily scan + "Scan now", keyword filter, Gemini extraction with
  keyword fallback.
- Change: **no admin approval.** A change Gemini extracted is sent at once to the businesses it affects (tray + email)
  and their active CAs (tray), recorded in `regulatory_change_matches` (which also drives the CA urgency points for 30
  days). A keyword-only change is saved and listed, but nobody is notified.
- New page **Regulatory updates** (business and CA): changes that concern your forms, newest first; keyword-only ones
  marked "Found by keywords: read the article".
- Admin page: sources, Scan now, list of found changes (no Approve/Reject). `status`, `reviewed_at`,
  `reviewed_by_id` columns removed; `notified_at` added on the change.

### assistant
- Keep: knowledge base ingest, pgvector search with the 0.40 cut-off, answer with citations, keyword fallback,
  "Ask a CA", history + clear. Shorter code.

### admin
- Keep: dashboard counts + filing stats, user list with search, CA list / detail / certificate / verify / reject.
- Remove: suspend, reactivate, audit log (table `admin_audit_log`, page, endpoints).

### Removed endpoints (and their frontend calls)
`POST /auth/accept-terms`, `POST /admin/users/<id>/suspend`, `/reactivate`, `GET /admin/audit-log`,
`GET/PUT /alerts/settings` (replaced by `GET/PUT /api/v1/auth/settings` `{email_notifications}`),
`POST /admin/regulatory/changes/<id>/approve`, `/reject`. New: `GET /api/v1/regulatory/updates`.

---

## 5. Safety net (how we make sure nothing breaks)

1. **Freeze.** Nobody starts other feature work until step 9 is done. All work goes through this plan's steps.
2. **Baseline tag.** Before step 1: `git tag before-simplify` on main, and write down that all tests pass.
3. **API snapshot (temporary script).** Before step 1, run a small script (`api_snapshot.py`, deleted at the end) that
   logs in as the demo business, CA and admin on a fresh `seed-demo` database, calls every GET endpoint and saves the
   JSON **keys and value types** (not the values: ids and dates change). After each step, run it again and diff. Any
   difference must be an item in section 4.
4. **Tests are the contract.** Each PR keeps the full suite green: `docker compose exec backend pytest` and
   `docker compose exec frontend npm test`, plus `npm run build`. A changed or deleted test must name the section 4
   item it belongs to in the PR description.
5. **Keep function names while converting.** When a module is rewritten, the functions other modules call keep their
   name and arguments (list in section 7). This is what lets three people work in parallel.
6. **Manual demo walk after each step** (10 minutes, README "Demo script"): signup + code in Mailpit, register a
   business, filing page (tick, mark filed with an acknowledgement → verified), vault, Find a CA → request, CA accepts
   / quotes, CA client page (ask for a document, mark filed), pro-bono, assistant, admin verifies a CA, Scan now.
7. **One PR per step (per module in step 4)**, reviewed by a teammate, merged only when green.

---

## 6. Steps

When run by one Claude Code session (section 11), the "Who" column is ignored: every step is done in order by the
same session, and the step 4 modules one after another (auth, onboarding, compliance, documents, alerts,
marketplace, ca_workspace, regulatory, assistant, admin, then `worker.py`). Step 9 is done by a person.

| # | Step | Who (if split by hand) | Size |
|---|---|---|---|
| 0 | Baseline: tag, snapshot script, note passing tests | Anurag | 1–2 h |
| 1 | Docker Compose, delete tooling | Anurag | half day |
| 2 | Cross-cutting removals (section 4 "Cross-cutting" + removed features) | Anurag | 1–2 days |
| 3 | Mechanical merge into the new file layout (no logic change) | Anurag | 1 day |
| 4 | Per module: plain Flask + simplify (parallel) | all three | 3–5 days |
| 5 | Remove flask-smorest/marshmallow, final backend cleanup | one person | half day |
| 6 | Frontend: merge files, update pages for section 4 | one person, parallel from step 3 | 2–3 days |
| 7 | eval scripts, demo seed, README, new CLAUDE.md | one person | half day |
| 8 | One fresh migration | Anurag | 1–2 h |
| 9 | Move to Neon | Anurag | 2–3 h |

### Step 1: Docker Compose, delete tooling
- Add `docker-compose.yml` (section 9). Change `main.py` to listen on `0.0.0.0`, and `vite.config.js` to proxy `/api`
  to `process.env.API_URL || "http://127.0.0.1:8000"`.
- `.env.example`: `DATABASE_URL` points to the `db` container for now; add placeholders for the shared secrets.
- Delete the files listed in section 3 "Repo root". CI: install from `backend/requirements.txt`, drop the ruff,
  ESLint and Prettier steps (and the OpenAPI step in step 5); keep pytest, `npm test`, `npm run build`.
- Done when: `docker compose up` starts everything, `seed-demo` works, the demo walk works, tests pass inside the
  containers.

### Step 2: Cross-cutting removals (old structure still)
Do them in this order, running the tests after each:
1. Delete `migrations/versions/*`; backend start runs nothing automatically. Add `flask reset-db` (drop all, create
   all, seed) for development; tests already create tables from the models. In CI, remove the "Migrations apply
   cleanly" step until step 8 brings the single migration back.
2. Rate limiting, row locking, anti-enumeration (section 4 auth).
3. Soft delete → real delete, partial indexes → UNIQUE.
4. Enums → String columns.
5. Unused tables/columns, suspend + audit log, matching score, email settings → `users.email_notifications`,
   regulatory approval → auto-notify (backend side), filing page not opening the file.
6. Files into `documents.content`.
- Done when: tests pass (only section 4 tests changed), snapshot diff shows only section 4 items.

### Step 3: Mechanical merge (no logic change)
- `models/*.py` → `models.py`; `utils/*` → `utils.py` + `ocr.py`; `config.py`, `extensions.py`, `errors.py` →
  `__init__.py` / `utils.py`; email templates → one dict in `utils.py`.
- For each module: `routes/<m>.py` + `schemas/<m>.py` + `services/<m>_service.py` → `app/<m>.py`, still using
  flask-smorest for now. Update imports in the other modules, `worker.py`, seeds, tests and `eval/`.
- Frontend file merges (section 3) can start now in parallel (step 6).
- Done when: same tests pass with only import changes.

### Step 4: Per module, plain Flask + simplification (parallel)
Suggested split:
- **Person A:** auth, onboarding, compliance, documents
- **Person B:** marketplace, ca_workspace, admin
- **Person C:** alerts, regulatory, assistant, `worker.py`, then the frontend (step 6)

For each module:
1. Replace `MethodView` + schemas with plain routes. Validation is a few `if` checks; keep the rules that exist
   today (formats, required fields, ranges).
2. Write `to_dict` helpers that produce exactly today's JSON.
3. Apply the module's section 4 items and the style rules of section 2 (rewrite docstrings and comments).
4. Remove dead code: a function nobody calls is deleted.
- Done per module when: its tests pass, the snapshot for its endpoints is unchanged (except section 4), and the demo
  walk for its screens works.

### Step 5: Final backend cleanup
Remove `flask-smorest` and `marshmallow` from `requirements.txt`, the OpenAPI settings and the CI step. Check that
nothing imports `app.services`, `app.routes`, `app.schemas`, `app.models.<x>` or `app.utils.<x>` any more.

### Step 6: Frontend
- File merges as in section 3 (no behaviour change first, tests updated for imports).
- Then: remove the audit log page, suspend buttons, the "Why this CA" box and ranking badges; replace the two
  notification settings pages with `SettingsPage`; remove the consent gate; the Regulatory admin page loses
  Approve/Reject; add the Regulatory updates page + nav link; update the "What changed" box.
- Style: same as section 2 (short components, no clever abstractions, plain comments).

### Step 7: The rest
- `eval/*/evaluate.py`: update imports to the new module functions; run each with `--keywords-only`.
- `demo_seed.py`: files go into the database; no suspend/audit data.
- README: "what it is" + `docker compose up` instructions + the demo script. New `CLAUDE.md` (section 8).
  Old CLAUDE.md moves to `docs/old-CLAUDE.md` (kept, as agreed).

### Step 8: One fresh migration
- On an empty local database: `docker compose exec backend flask --app app db migrate -m "initial schema"`. Check it
  by hand: `CREATE EXTENSION IF NOT EXISTS vector` at the top, `sa.Text()` for encrypted columns,
  `import pgvector.sqlalchemy` for the vector column.
- `flask db upgrade` on an empty database, then `flask db check` must say no changes. Tests pass.

### Step 9: Move to Neon
1. Create a Neon project in **AWS Singapore (ap-southeast-1)**, Postgres **16** (same as tests and CI).
2. Copy the **direct** connection string (not the `-pooler` one) and write it as
   `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/neondb?sslmode=require`.
3. Make one shared `.env` with `DATABASE_URL`, `FIELD_ENCRYPTION_KEY`, `SECRET_KEY`, `JWT_SECRET_KEY` and share it
   privately (not in git). **All three must use the same encryption key**, or nobody can read the others' PAN/GSTIN.
4. Anurag only, once: `flask db upgrade`, `flask seed-demo`, `flask assistant ingest`.
5. Team rules from now on: only one person runs migrations on Neon, and only from main. Only one person runs the
   worker (`docker compose --profile worker up`). Tests always use the `db` container (the fixture refuses to run if
   `TEST_DATABASE_URL` equals `DATABASE_URL`).
6. Demo walk from all three laptops on the same data.

Expect Neon to be slower than a local database (Singapore is the closest region; the first request after 5 idle
minutes wakes the database up). Free plan: 0.5 GB storage, 100 compute-hours a month; our data is a few MB.

---

## 7. Functions other modules call (keep these names during step 4)

| Module | Functions |
|---|---|
| compliance | `list_filings`, `get_filings_by_ids`, `mark_filings_with_ca`, `checklist_keys`, `checklist_with_ticks`, `checklist_progress`, `tick_checklist_entry`, `mark_filed_by_ca`, `filings_by_acknowledgement`, `list_unfiled_filings_due_by`, `business_ids_with_open_filings`, `create_filings`, `sync_filings`, `filing_stats`, `FORM_FOLDERS`, `DONE_STATUSES` |
| onboarding | `get_business`, `business_of_user`, `get_my_business`, `get_msme_tier`, `get_itr_form`, `business_categories`, `business_ids_in_segment`, `count_businesses` |
| documents | `add_document`, `read_document`, `remove_document`, `document_ids_for_filings`, `attach_document`, `documents_by_filing`, `verify_acknowledgement`, `GENERAL_KEY` |
| marketplace | `own_profile_id`, the access checks (renamed once, in step 4, by Person B together with their callers), `active_work`, `active_cas_of_business`, `active_ca_users_by_filing`, `complete_if_all_filed`, `open_filing_ids`, `list_cas_for_admin`, `get_ca_for_admin`, `certificate_document_id`, `set_verification`, `count_cas_by_status`, `count_open_engagements` |
| alerts / utils | `notify` |
| regulatory | `active_changes_for`, `forms_text`, `scan_news` |
| auth | `list_users`, `count_users_by_role` |

---

## 8. New CLAUDE.md (replace the old one in step 1)

```markdown
# CA Helper
Flask + React + Postgres (Neon) lab project. Keep it simple: a beginner should be able to read any file.

Run: `docker compose up` (app http://localhost:5173, API :8000, Mailpit :8025).
Tests: `docker compose exec backend pytest`, `docker compose exec frontend npm test`.

While SIMPLIFICATION_PLAN.md exists, follow it: do only the step you are asked to do.

Code style:
- Backend: plain Flask routes in app/<feature>.py; models in app/models.py; helpers in app/utils.py.
- Short functions, plain loops, one-line docstrings, comments only for the "why". No task ids or rule numbers.
- Keep the JSON responses and error codes the frontend uses.
- Commit in the route before returning. Send emails after the commit.
- Never send PAN, GSTIN, names or document text to Gemini (utils.ask_gemini scrubs them).
- OCR stays local. Legal thresholds and due dates come from the rule tables, never from code.
- Frontend: plain JS, pages in pages/, all API calls in api.js.
- Never point TEST_DATABASE_URL at Neon. Never commit .env.
```

---

## 9. docker-compose.yml (target, needs Docker Compose 2.17+)

```yaml
# docker compose up                   app, API, Mailpit, test database
# docker compose --profile worker up  also the scheduled jobs (only ONE teammate runs this)
# App http://localhost:5173 · API http://localhost:8000 · Mail http://localhost:8025
x-backend: &backend
  build:
    context: ./backend
    dockerfile_inline: |
      FROM python:3.12-slim
      RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
          && rm -rf /var/lib/apt/lists/*
      COPY requirements.txt ./
      RUN pip install --no-cache-dir -r requirements.txt
  volumes: [".:/app"]
  working_dir: /app/backend
  env_file: .env                       # DATABASE_URL = Neon (the local db until step 9)
  environment:
    TEST_DATABASE_URL: postgresql+psycopg://ca_helper:ca_helper_dev@db:5432/ca_helper_test
    MAIL_SERVER: mailpit
    MAIL_PORT: "1025"
  depends_on:
    db: { condition: service_healthy }

services:
  db:                                   # tests only after step 9
    image: pgvector/pgvector:pg16
    environment: { POSTGRES_USER: ca_helper, POSTGRES_PASSWORD: ca_helper_dev, POSTGRES_DB: ca_helper }
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck: { test: ["CMD", "pg_isready", "-U", "ca_helper"], interval: 3s, retries: 20 }

  mailpit:
    image: axllent/mailpit:v1.31
    ports: ["8025:8025"]

  backend:
    <<: *backend
    command: python main.py
    ports: ["8000:8000"]

  worker:
    <<: *backend
    command: python worker.py
    profiles: ["worker"]

  frontend:
    build:
      context: ./frontend
      dockerfile_inline: |
        FROM node:22
        WORKDIR /app/frontend
        COPY package.json package-lock.json ./
        RUN npm ci
    volumes: ["./frontend:/app/frontend", "/app/frontend/node_modules"]
    environment: { API_URL: "http://backend:8000" }
    command: npm run dev -- --host 0.0.0.0
    ports: ["5173:5173"]

volumes:
  pgdata:
```

Commands: `docker compose exec backend flask --app app db upgrade | seed | seed-demo | reset-db | assistant ingest`.
After changing `requirements.txt` or `package.json`: `docker compose up --build`.

---

## 10. Risks and how they are handled

| Risk | Handling |
|---|---|
| A response changes shape and a page breaks silently | API snapshot diff (5.3) + frontend tests + demo walk after every step |
| Three people editing the same files | Steps 2–3 done by one person before parallel work; step 4 split by module; function names kept (section 7) |
| Tests start failing for real reasons and get "fixed" by editing the test | Rule 5.4: a test may only change for a section 4 item, named in the PR |
| Teammates' encryption keys differ on Neon | One shared `.env` (step 9.3) |
| Tests wipe the shared database | Tests use the `db` container; the fixture refuses Neon |
| Worker jobs run three times | Worker only via `--profile worker`, one person |
| Gemini quota runs out on viva day | One fallback per AI feature kept |
| Something turns out to be needed after all | `git tag before-simplify` keeps the old version; copy the piece back |

---

## 11. The Claude Code prompts

### Before you start
- Put this file in the repo root of an up-to-date `main`. Teammates stop pushing to main until the PR is merged.
- Docker Desktop running; the current dev setup still working (`make infra`, `make test`) for step 0.
- `gh auth login` done (for the PR at the end).
- Start Claude Code in the repo with the strongest model available.

### The one-shot prompt

```
Simplify this repository (CA Helper) end to end by following SIMPLIFICATION_PLAN.md in the repo root.
Read the whole plan first: it is the specification. Sections 2 (style), 4 (the ONLY allowed behaviour
changes), 5 (safety net) and 7 (function names to keep) are binding.

HOW TO WORK
1. Do steps 0 to 8 of section 6 yourself, in order. Ignore the "Who" column. In step 4 do the modules
   one by one: auth, onboarding, compliance, documents, alerts, marketplace, ca_workspace, regulatory,
   assistant, admin, then worker.py. Do NOT do step 9 (Neon).
2. Git: on an up-to-date main run `git tag before-simplify` and push the tag, then create the branch
   `simplify`. Never commit to main, never force-push, never merge.
3. Keep SIMPLIFY_PROGRESS.md in the repo root. After every step (and every module in step 4) update it:
   what was done, test results, the snapshot diff result, EVERY test you changed or deleted with the
   section 4 item it belongs to, and anything you were unsure about. Before starting each step, re-read
   SIMPLIFICATION_PLAN.md and SIMPLIFY_PROGRESS.md, so you stay correct after a long session or a
   context reset.
4. After every step / module run: backend tests, frontend tests, `npm run build`, and the API snapshot
   compare. Fix until everything is green. Then commit (small Conventional Commits, e.g.
   "refactor(compliance): plain Flask routes") and push the branch.
5. A failing test may only be changed or deleted if it tests a section 4 item. Otherwise the code is
   wrong: fix the code, not the test. Only import paths may change freely.
6. Keep the JSON contract exactly: URLs, keys, value formats (money "1250.00", dates, ISO timestamps,
   ids as strings, lowercase codes) and error codes, except the endpoints section 4 removes or adds.
7. Do not add any new package. Remove packages only where the plan says. Do not touch docs/ (except
   moving CLAUDE.md to docs/old-CLAUDE.md), content/ or the eval/ datasets.
8. STOP and ask me (write the question in SIMPLIFY_PROGRESS.md first) when: the plan is ambiguous; a
   change would alter behaviour not listed in section 4; something still fails after 3 honest attempts;
   or you want to delete something the plan does not list. Never guess about behaviour.

STEP 0 DETAILS
- With the current tooling (make infra, make test) confirm every test passes on main. If not, stop and
  tell me.
- Write api_snapshot.py (temporary, repo root, deleted in step 7). On an empty database it runs the
  seed and the demo seed, logs in as the demo business, CA and admin (passwords from .env), calls every
  GET endpoint (path ids taken from list responses) and saves, per endpoint, the JSON STRUCTURE: keys and
  value types (string / number / bool / null / list / object; 2-decimal money strings as "money"), not
  the values. `python api_snapshot.py --compare` prints the differences from the saved baseline.
  Save the baseline on main, before any change.

FINISH
When step 8 is done and everything is green: delete api_snapshot.py and its output, keep
SIMPLIFY_PROGRESS.md, push, and open a pull request "Simplify the codebase" from `simplify` to main
(do not merge). Then give me: files and lines before/after (backend, frontend, tests), every behaviour
change, every changed or deleted test with its reason, which parts of the demo walk (section 5.6) you
verified yourself (through the API) and which I must click through in the browser, and the step 9
(Neon) instructions.
```

### If the session stops (usage limit, closed terminal, context reset)

```
Continue the CA Helper simplification. Read SIMPLIFICATION_PLAN.md and SIMPLIFY_PROGRESS.md, check
`git status` and `git log` on the simplify branch, finish or redo the last unfinished step, then carry on
with the same rules as before until step 8 is done.
```
