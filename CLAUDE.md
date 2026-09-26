# CA Helper: context for every Claude Code session

**Product (report title "ComplianceConnect"):** a two-sided web platform for Indian MSMEs, gig workers and small
businesses. It tells each business which filings apply and when (ITR, GSTR-1, GSTR-3B, CMP-08, GSTR-4, 24Q, 26Q),
guides self-filing or connects them to a fairly priced or pro-bono CA, and keeps verifiable proof of filing.
It never files returns itself (no government API): it tracks, guides, connects and verifies. Roles: Business, CA,
Admin. 3-person MTech CSE lab project (IIT Bombay); every file must be explainable in a viva, so keep it boring.

@docs/SCOPE.md

## Stack and how it runs
- Backend: Python 3.12 (conda env `ca-helper`), Flask 3 app factory, flask-smorest (OpenAPI, Swagger at `/api/docs`),
  Flask-SQLAlchemy 2.x style + Flask-Migrate, JWT, Flask-Limiter, Postgres 16 (psycopg 3), argon2, APScheduler in a
  **separate worker process**.
- Frontend: React + Vite + **JavaScript (`.js`/`.jsx`, no TypeScript)**, React Router, TanStack Query, Tailwind +
  shadcn/ui, React Hook Form + Zod, `apiFetch()` (fields per Swagger at `/api/docs`), Vitest + RTL.
- Added with their features, not installed yet: pgvector, google-genai (Gemini), Fernet + HMAC blind index, Tesseract +
  PyMuPDF (never pdfplumber as well), a calendar and a chart library (ask which first).
- Run: `make infra` (Postgres + Mailpit in Docker), `make dev-backend` (`python main.py`), `make dev-worker`,
  `make dev-frontend` (Vite forwards `/api` to Flask); all read the root `.env`. `make help` lists every target.
  People may run the servers by hand (README "Quick start"); Claude always uses Make targets or `conda run`.
- Ports: API 8000, Vite 5173, Postgres 5432, Mailpit UI 8025. Node 22 LTS from the conda env.
- Ask before substituting or adding any tool. Record decisions in `docs/DECISIONS.md`.

## Folder map
```
backend/app/__init__.py      create_app() · config.py extensions.py errors.py seed.py (`flask seed`)
backend/app/models/          base.py (BaseModel, mixins) enums.py <m>.py · __init__.py imports every model
backend/app/schemas/         <m>.py (marshmallow request/response shapes)
backend/app/services/        <m>_service.py (business logic, all DB access)
backend/app/routes/          <m>.py (one Blueprint each) · __init__.py: BLUEPRINTS list, /api/v1 prefix
backend/app/utils/           decorators.py (role checks) jwt_handlers.py passwords.py
backend/tests/               test_*.py · conftest.py shared pytest fixtures
backend/main.py              dev server entrypoint (`python main.py`)
backend/worker.py            APScheduler entrypoint (every job listed in build_scheduler())
backend/migrations/          single Alembic dir
frontend/src/routes.jsx      every page route + sidebar links (NAV) · main.jsx
frontend/src/api/            client.js (apiFetch) <m>.js (query hooks)
frontend/src/pages/          HomePage LoginPage NotFoundPage · business/ ca/ admin/ (one folder per role)
frontend/src/components/     ui/ (shadcn) AppShell PublicLayout RequireRole Placeholder
frontend/src/context/ hooks/ AuthProvider · useAuth       frontend/src/lib/  session labels queryClient utils
frontend/src/test/           setup.js (Vitest setup) utils.jsx (render helpers)
content/forms/<FORM>/        explanation.md instructions.md checklist.yaml
docs/                        project docs · docs/modules/<m>.md = module context (what exists, contracts)
eval/                        evaluation datasets (never real personal data) · scripts/ setup_dev.sh
```
Folders are by layer; a module is the set of same-named files across them (`models/<m>.py`, `schemas/<m>.py`,
`services/<m>_service.py`, `routes/<m>.py`, `tests/test_<m>_*.py`, `api/<m>.js`, `pages/<role>/...`). Only create a
file when it has code. Registration is explicit: `BLUEPRINTS`, `models/__init__.py`, `SEEDS`, `routes.jsx`, `worker.py`.
Modules: onboarding, compliance, alerts, documents, assistant, regulatory, marketplace, ca_workspace, admin.
Foundation docs: `core-auth.md` (auth), `core-infra.md` (shared backend + dev setup), `frontend-core.md`.
**Shared code** (used by every module): `app/{__init__,config,extensions,errors,seed}.py`, `models/{base,enums}.py`,
`routes/__init__.py`, `utils/`; frontend `routes.jsx`, `api/client.js`, `components/`, `context/`, `hooks/`, `lib/`.

## Conda rules
1. Miniforge / conda-forge only: `environment.yml` uses `channels: [conda-forge, nodefaults]`.
2. Conda installs only `python=3.12`, `nodejs=22`, `pip`. **All Python packages come from pip via
   `backend/requirements*.txt`** (CI uses the same files). Never `conda install` a Python library; never
   pip-install anything that isn't in a requirements file. npm packages come from `frontend/package-lock.json`.
3. One shared `environment.yml` (env `ca-helper`; its pip section installs `-r backend/requirements-dev.txt`).
   After dependency changes: `make env-update`.
4. **Every Python and Node command runs via `conda run -n ca-helper <cmd>`** (`--no-capture-output` for servers;
   `--cwd backend` / `--cwd frontend`). Never rely on an activated env; never use system Python, pip, Node or nvm.
5. `.vscode/settings.json` points at the env via the `.conda-env` link (no user paths); README covers manual selection.

## Non-negotiable rules
**Simplicity first:** build the simplest thing that works and is explainable in 1–2 sentences. Don't add
infrastructure, tooling or abstraction layers without asking.

1. **No PII to Gemini.** Never send PAN, GSTIN, TAN, names, emails, phones, addresses or document contents. Every
   Gemini call goes through `backend/app/utils/gemini_client.py`, which regex-scrubs PAN/GSTIN/email/phone/
   Aadhaar-like patterns and logs a warning when it finds any.
2. **OCR is local only** (Tesseract/PyMuPDF). Documents never leave our server.
3. **Legal rules are data, not code:** thresholds, due-date rules and applicability live in DB config tables with
   `source_reference`, `effective_from`, `effective_to`. **Never invent a legal threshold, rate or due date.**
   Unconfirmed values get `TODO_VERIFY` in `source_reference` and a row in `docs/TODO_VERIFY.md`.
4. **Sensitive fields are encrypted:** PAN, GSTIN, TAN, phone and uploaded files use `EncryptedString` and
   encrypted file storage. Passwords are hashed (argon2), never encrypted.
5. **Access control on every endpoint** via shared role decorators. A CA reads a business's data only through
   `ca_has_active_access(ca_id, business_id)`.
6. **Soft delete only** (`is_active` / `deleted_at`).
7. **Money:** `Decimal`, stored `Numeric(12,2)` rupees. **Time:** store UTC, display Asia/Kolkata.
   Financial year = April–March.
8. **Secrets only in `.env`** (gitignored). Every new variable goes into `.env.example` with a comment.
9. **Cross-module reads go through service functions**, never direct imports of another module's models in routes.
10. **Layering:** routes parse, call one service function, serialize; services hold the logic and each public one
   commits once at its end; models (subclass `BaseModel`) hold data only. Module routes live under `/api/v1`.
   Enums are `StrEnum` with lowercase snake_case values stored via `str_enum()`. See `docs/PATTERNS.md` "Foundations".

## Session checklist
**Start**
1. `git status`: if there are uncommitted changes you didn't make in this task, **stop and ask**.
2. `git fetch origin`, then `git switch main && git pull --ff-only`.
3. New task: `git switch -c <name>/<module>-<short-task>` (e.g. `anurag/documents-ack-upload`). Continuing: switch,
   then `git rebase origin/main`. A conflict in files you didn't change in this task → **stop and ask**.
4. Read `docs/modules/<module>.md` and `docs/PATTERNS.md`.
5. Summarize what changed on main that matters here (`docs/`, `backend/migrations/`, shared code, "Depends on").
6. Env check: env `ca-helper` exists (else tell the user to run `make setup`); `environment.yml`/`requirements*`
   changed → `make env-update`; `frontend/package*.json` changed → `conda run -n ca-helper --cwd frontend npm ci`;
   `make infra` running; `make migrate` and `make test` pass **before** changing anything.

**While working**
- Keep changes scoped to the task; if a change touches shared code, shared config, or another module, say so clearly
  in the PR. Follow `docs/PATTERNS.md`; copy the closest existing example.
- **The repo is the single source of truth:** anything decided in chat that affects others goes into `docs/`
  (module doc, `DECISIONS.md`, `DATA_MODEL.md` or `API_CONVENTIONS.md`) in the same PR.
- Small Conventional Commits (`feat(documents): ...`, `fix(...)`, `docs(...)`, `test(...)`, `chore(...)`); stage
  specific files, never `git add -A` blindly.
- Migrations: pull main right before `make migration name="<module>: <msg>"`; one per PR; never edit a migration
  already on main; multiple heads → `conda run -n ca-helper --cwd backend flask --app app db merge heads -m "merge"`.
- Route/schema change → check every frontend call of that endpoint (`grep` the URL in `frontend/src/api/`).
- New dependency (ask first): pin in `backend/requirements*.txt` + `make env-update`, or `conda run -n ca-helper
  --cwd frontend npm install <pkg>`; mention it in the PR. New service/route → tests; new table → seed data.

**End / before a PR**
- `make lint` and `make test` pass and the frontend builds (`conda run -n ca-helper --cwd frontend npm run build`).
  Never leave the branch red.
- Update the module doc: "What exists now", tables, endpoints, contracts, known issues. Data model or
  conventions changed → `docs/DATA_MODEL.md` / `docs/DECISIONS.md`.
- Show a summary and **ask before `git push`**; PR from `.github/pull_request_template.md` (`gh pr create`), one task
  per PR. CI green and a teammate's review before a squash-merge into `main`.

**Never:** commit to main · force-push main · rewrite a branch someone else uses · `git reset --hard` or delete
branches without asking · commit secrets or generated files (`.env`, `openapi.json`, uploads).

## Other docs (read when relevant)
`docs/PATTERNS.md` (how to add a feature) · `docs/API_CONVENTIONS.md` (URLs, auth, errors, pagination) ·
`docs/DATA_MODEL.md` (tables, status values) · `docs/DECISIONS.md` (decision log) · `docs/TODO_VERIFY.md`
(unverified legal values) · `docs/modules/_TEMPLATE.md` · `README.md` (setup)
