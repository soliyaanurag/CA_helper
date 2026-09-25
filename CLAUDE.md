# CA Helper: context for every Claude Code session

**Product (report title "ComplianceConnect"):** a two-sided web platform for Indian MSMEs, gig workers and small
businesses. It tells each business which filings apply and when (ITR, GSTR-1, GSTR-3B, CMP-08, GSTR-4, 24Q, 26Q),
guides self-filing or connects them to a fairly priced or pro-bono CA, and keeps verifiable proof of filing.
It never files returns itself (no government API): it tracks, guides, connects and verifies. Roles: Business, CA,
Admin. 3-person MTech CSE lab project (IIT Bombay); every file must be explainable in a viva, so keep it boring.

@docs/SCOPE.md

## Stack and run modes
- Backend: Python 3.12 (conda env `ca-helper`), Flask 3 app factory, flask-smorest (OpenAPI, Swagger at `/api/docs`),
  Flask-SQLAlchemy 2.x style + Flask-Migrate, JWT, CORS, Limiter, Postgres 16 + pgvector (psycopg 3), argon2,
  Fernet + HMAC blind index, APScheduler in a **separate worker process**, google-genai, Tesseract/PyMuPDF/pdfplumber/OpenCV.
- Frontend: React + Vite + TypeScript, React Router, TanStack Query, Tailwind + shadcn/ui, React Hook Form + Zod,
  openapi-typescript + openapi-fetch (types generated, never hand-written), FullCalendar, Recharts, Vitest + RTL.
- **Hybrid mode (daily):** `make infra` (db + Mailpit in Docker) + `make dev-backend` / `dev-worker` / `dev-frontend`.
  **Full-Docker (`make up`):** all 5 services; must always work. Both read the same root `.env` (hostnames differ).
  **Manual (for people, not Claude):** `conda activate ca-helper` + `cd backend && python main.py` + `npm run dev` (README
  "Quick start (manual)"). Claude itself always uses Make targets or `conda run`.
- Ports: API 8000, Vite 5173, Docker frontend 8080, Postgres 5432, Mailpit UI 8025. Node 22 LTS from the conda env.
- Ask before substituting any tool. Record decisions in `docs/DECISIONS.md`.

## Folder map
```
backend/app/__init__.py      create_app(); config.py, extensions.py, cli.py (`flask seed`)
backend/app/core/            auth/ permissions.py db/ security/ storage/ email/ notifications/ ai/ ocr/ errors.py health.py
                             logging_config.py request_id.py · db/: base.py models.py (BaseModel, mixins) enums.py
backend/app/modules/<m>/     __init__.py (blp, seed, register_jobs) routes.py models.py schemas.py services.py seed.py tests/
backend/worker.py            APScheduler entrypoint (collects each module's register_jobs) · gunicorn.conf.py
backend/migrations/          single Alembic dir · backend/conftest.py shared pytest fixtures
frontend/src/core/           api/ (client.ts, generated/ gitignored) auth/ layout/ components/ui/ routes.tsx labels.ts
frontend/src/features/<m>/   routes.tsx pages/ components/ hooks/ api.ts admin/
content/forms/<FORM>/        explanation.md instructions.md checklist.yaml
docs/                        project docs · docs/modules/<m>.md = module context (what exists, contracts)
eval/                        evaluation datasets (never real personal data) · scripts/ setup_dev.sh
```
Modules: onboarding, compliance, alerts, documents, assistant, regulatory, marketplace, ca_workspace, admin.

## Conda rules
1. Miniforge / conda-forge only: `environment.yml` uses `channels: [conda-forge, nodefaults]`.
2. Conda installs only `python=3.12`, `tesseract`, `nodejs=22`, `pip`. **All Python packages come from pip via
   `backend/requirements.txt` / `requirements-dev.txt`** (Docker and CI use the same files). Never `conda install`
   a Python library; never pip-install anything that isn't in a requirements file. npm packages come from
   `frontend/package-lock.json`.
3. One shared `environment.yml` (env `ca-helper`; its pip section installs `-r backend/requirements-dev.txt`).
   After dependency changes: `make env-update`.
4. **Every Python and Node command runs via `conda run -n ca-helper <cmd>`** (`--no-capture-output` for servers;
   `--cwd backend` / `--cwd frontend`). Never rely on an activated env; never use system Python, pip, Node or nvm.
5. `.vscode/settings.json` points at the env via the `.conda-env` link (no user paths); README covers manual selection.
6. OCR tests use `@pytest.mark.requires_tesseract`, which skips with a clear message if Tesseract is missing.

## Non-negotiable rules
1. **No PII to Gemini.** Never send PAN, GSTIN, TAN, names, emails, phones, addresses or document contents. Every
   Gemini call goes through `backend/app/core/ai/gemini_client.py`, which regex-scrubs PAN/GSTIN/email/phone/
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

## Key commands
`make setup` · `make env-update` · `make infra` / `infra-down` · `make dev-backend` / `dev-worker` / `dev-frontend` ·
`make up` / `down` / `logs` · `make test` (`test-backend`, `test-frontend`) · `make lint` / `format` ·
`make migrate` · `make migration name="<module>: <msg>"` · `make seed` · `make gen-api`

## Session checklist (details: docs/WORKFLOW.md)
**Start**
1. `git status`: if there are uncommitted changes you didn't make in this task, **stop and ask**.
2. `git fetch origin`, then `git switch main && git pull --ff-only`.
3. New task: `git switch -c <name>/<module>-<short-task>`. Continuing: switch, then `git rebase origin/main`.
   A conflict in files you didn't change in this task → **stop and ask**.
4. Read `docs/modules/<module>.md` and `docs/PATTERNS.md`.
5. Summarize what changed on main that matters here (`docs/`, `backend/migrations/`, `backend/app/core/`,
   `frontend/src/core/`, modules under "Depends on").
6. Env check: env `ca-helper` exists (else tell the user to run `make setup`); `environment.yml`/`requirements*`
   changed → `make env-update`; `frontend/package*.json` changed → `conda run -n ca-helper --cwd frontend npm ci`; `make infra` running;
   `make migrate`, `make gen-api` and `make test` pass **before** changing anything.

**While working**
- Keep changes scoped to the task; if a change touches `core/`, shared config, or another module, say so clearly
  in the PR. Follow `docs/PATTERNS.md`; copy the closest existing example.
- **The repo is the single source of truth:** anything decided in chat that affects others goes into `docs/`
  (module doc, `DECISIONS.md`, `DATA_MODEL.md` or `API_CONVENTIONS.md`) in the same PR.
- Small Conventional Commits (`feat(documents): ...`); stage specific files, never `git add -A` blindly.
- Migrations: pull main right before `make migration`; one per PR, message prefixed with the module; never edit a
  migration already on main; multiple heads → create a merge revision.
- Route/schema change → `make gen-api` and fix type errors in your features.
- New dependency: pin in `backend/requirements*.txt` + `make env-update`, or `conda run -n ca-helper --cwd frontend npm install <pkg>`;
  mention it in the PR. Every new service/route gets tests; every new table gets seed data.

**End / before a PR**
- `make lint` and `make test` pass and the frontend builds. Never leave the branch red.
- Update the module doc: "What exists now", tables, endpoints, contracts, known issues. Data model or
  conventions changed → `docs/DATA_MODEL.md` / `docs/DECISIONS.md`.
- Show a summary and **ask before `git push`**; draft the PR from `.github/pull_request_template.md`.

**Never:** commit to main · force-push main · rewrite a branch someone else uses · `git reset --hard` or delete
branches without asking · commit secrets or generated files (`.env`, `openapi.json`, `frontend/src/core/api/generated/`, uploads).

## Other docs (read when relevant)
`docs/WORKFLOW.md` (git + sessions) · `docs/PATTERNS.md` (how to add a feature) · `docs/API_CONVENTIONS.md`
(URLs, auth, errors, pagination) · `docs/DATA_MODEL.md` (tables, status values) · `docs/DECISIONS.md` (decision log) ·
`docs/TODO_VERIFY.md` (unverified legal values) · `docs/modules/_TEMPLATE.md` · `README.md` (setup)
