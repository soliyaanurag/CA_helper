# Decision log

Newest first. One entry per decision: date, what, why. Anything decided in chat that affects others goes here
in the same PR.

## 2026-09-25: Phase 0 bootstrap (Builder)

**Stack and versions**
- **Stack as specified in the bootstrap prompt**; direct dependencies pinned exactly in
  `backend/requirements*.txt` and `frontend/package.json` (`.npmrc` has `save-exact=true`).
- **Node 22 LTS, not 20.** react-router 8, vitest 5 and jsdom 30 require Node ≥ 22.12 to 22.22. Enforced by `.nvmrc`
  (`22`), `package.json` `engines` (`>=22.22`) and `engine-strict=true`.
- **TypeScript 5.9, not 7.** typescript-eslint (peer `<6.1`) and openapi-typescript (peer `^5`) do not support TS 7 yet.
- **SQLAlchemy 2.0.x, not 2.1.** Flask-SQLAlchemy 3.1.1 predates SQLAlchemy 2.1.
- **FullCalendar 6.1, not 7.** v7 is a new headless rewrite whose plugin packages are not released for it; 6.1 is
  stable and well documented.
- **APScheduler 3.x** (`BlockingScheduler`, in-memory job store). Jobs are re-registered at worker start, so
  nothing needs to be persisted.
- **Gemini defaults:** `GEMINI_MODEL=gemini-3.8-flash`, `GEMINI_EMBED_MODEL=gemini-embedding-001` (current names
  on the Gemini models page on this date; change them in `.env` only).

**Approved small additions** (asked and approved)
- **python-dotenv**: `app/config.py` loads the root `.env`, so hybrid mode, the worker and pytest share it.
  Existing environment variables win (Docker/CI values are never overridden).
- **openapi-fetch**: typed client over the openapi-typescript types (`frontend/src/core/api/client.ts`).
- **nginx:alpine** serves the built frontend in full-Docker mode and proxies `/api` to the backend.
- shadcn/ui's own **`cn`** package (a clsx + tailwind-merge replacement), installed by `shadcn init`.

**Structure and conventions**
- **Shared pytest fixtures live in `backend/conftest.py`** (not `backend/tests/conftest.py`). pytest applies a
  conftest only to its own folder, and module tests live in `app/modules/<module>/tests/`.
- **Blueprints use `url_prefix="/api"`** and every route spells out its module segment (`/compliance/...`,
  `/admin/compliance/...`), so admin routes can live in the owning module's blueprint.
- **Module auto-discovery** (`app/modules/__init__.py`): each package exposes `blp`, optional `seed()`,
  `SEED_ORDER` (default 100) and `register_jobs(scheduler)`. `flask seed` commits once after all seeds.
- **Error format** `{"error": {"code", "message", "details?"}}` for every error, via a `flask_smorest.Api`
  subclass (`CaHelperApi`) plus an `ApiError` exception. Unhandled exceptions still show the debugger in dev and
  tracebacks in tests.
- **JSON is snake_case, money is a decimal string, timestamps are UTC ISO 8601** (docs/API_CONVENTIONS.md).
- **Worker cron times are Asia/Kolkata.** Every job is wrapped to run inside the Flask app context.
- **Alembic migration file names are date-prefixed** (`migrations/alembic.ini` `file_template`) so they sort in
  time order across members.
- **Frontend route aggregation** via `import.meta.glob("../features/*/routes.tsx")`. Each feature exports
  `routes: FeatureRoutes` keyed by area (`public`, `business` /app, `ca` /ca, `admin` /admin) with nav items.
- **shadcn/ui** initialised with the `radix-nova` preset; components live in `src/core/components/ui/`
  (`components.json` aliases point there).
- **Ruff config is one root `ruff.toml`** (backend and scripts share it); pytest config stays in `backend/pyproject.toml`.

**Environment and tooling**
- **Ports:** backend 8000 (macOS uses 5000 for AirPlay), Vite 5173, full-Docker frontend 8080, Postgres 5432
  (`DB_HOST_PORT`), Mailpit 1025/8025.
- **Generated API types are not committed**, so the frontend needs `make gen-api` before typecheck/build.
  The Makefile targets `dev-frontend`, `test-frontend`, `lint` and `up` run it first; `make setup` runs it once;
  CI passes the spec from the backend job to the frontend job.
- **VS Code interpreter:** `make setup` creates a gitignored `.conda-env` symlink to the env, and
  `.vscode/settings.json` points to `${workspaceFolder}/.conda-env/bin/python`. No user-specific paths.
- **Pre-commit Python hooks run ruff through `conda run -n ca-helper`** (local hooks), so they use the pinned
  version. Generic hooks come from `pre-commit/pre-commit-hooks`.
- **`make setup` also writes random dev secrets** (SECRET_KEY, JWT_SECRET_KEY, FIELD_ENCRYPTION_KEY,
  BLIND_INDEX_KEY) into a new `.env`, and generates API types at the end.
- **Any conda distribution works** (Miniforge recommended; Miniconda/Anaconda accepted). `environment.yml` uses
  `conda-forge` + `nodefaults`, so the `defaults` channel is never used.
- **CI** has three jobs: backend (ruff, tracker `--strict`, migrations, pytest with Postgres + Tesseract, OpenAPI
  export) → frontend (gen types, lint, format, typecheck, test, build) → docker (build all images, start
  full-Docker mode, smoke-test through nginx).
- **Git history** starts with one empty root commit on `main` (the GitHub repo was empty), so Phase 0 can be a
  normal PR from `chore/phase-0-bootstrap`.
