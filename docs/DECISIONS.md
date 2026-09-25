# Decision log

Newest first. One entry per decision: date, what, why. Anything decided in chat that affects others goes here
in the same PR.

## 2026-09-25: Basic login, role areas and manual run mode

**What**
- **Business area URL is `/business`** (was `/app`), so each role's area matches its name: `/business`, `/ca`,
  `/admin`. `AREA_PREFIX.business` in `frontend/src/core/routing.ts`; supersedes "`business` /app" in the
  bootstrap entry. Frontend contract change.
- **Area home endpoints stay module-owned**: `GET /api/v1/compliance/dashboard` (business),
  `/api/v1/ca-workspace/dashboard` (CA), `/api/v1/admin/dashboard` (admin), named for what they will become. No
  exception to `/api/v1/<module>/...`. Frontend pages: `BusinessDashboardPage`, `CaDashboardPage`,
  `AdminDashboardPage`, each registered as its area's `index` route by its module.
- **Access token only, in localStorage**, for this prototype (TODO in `frontend/src/core/auth/session.ts`: move to
  an httpOnly refresh-token cookie). Lifetime `JWT_ACCESS_TOKEN_MINUTES` (default 60).
- **Roles are checked against the database** in `roles_required`, not only the JWT claim; the JWT user loader
  rejects deactivated/deleted users on every request with **401 `ACCOUNT_INACTIVE`** (401, so the frontend logs
  out). Login itself returns 403 `ACCOUNT_INACTIVE`, and only after a correct password.
- **Unknown email and wrong password are indistinguishable**: same 401 `INVALID_CREDENTIALS`, and an unknown email
  still costs one argon2 verify (against a cached dummy hash). Outdated argon2 hashes are rehashed on login.
- **Bearer auth is the OpenAPI global default** (`API_SPEC_OPTIONS["security"]`); public endpoints opt out with
  `@blp.doc(security=[])` (health, login).
- **`users` and `UserRole` live in core** (`app/core/auth/`, `app/core/db/enums.py`); the demo-user seed is a core
  seed that `run_all_seeds()` runs before the module seeds.
- **Rate limiting stays on in tests**; `backend/conftest.py` resets the in-memory counters before each test.
  (With `RATELIMIT_ENABLED=False` Flask-Limiter registers no hooks, so the limit could not be tested.)
- **Login email is a plain string, not `fields.Email`**: the service trims and lowercases it, and a malformed
  email simply matches no user (401). The frontend validates the format with Zod.
- **Manual run mode:** `backend/main.py` (not `app.py`, which would shadow the `app` package) runs Flask's dev
  server on 127.0.0.1:8000 with debugger/reload from `DEV_SERVER_DEBUG` (on only in development), for people
  running `conda activate ca-helper && python main.py` by hand. Make targets, Docker and CI are unchanged, and
  scripts/Claude still use `conda run` or Make.
- **API client:** `baseUrl` is the page origin (no path) instead of `""`, and `fetch` is looked up per call, so
  frontend tests running in Node can build requests and stub `fetch`. Browser behaviour is the same.
- **shadcn `input` and `label`** added (no new npm packages).
- **One frontend error type:** every API call goes through `unwrap()` (`frontend/src/core/api/errors.ts`), which
  throws `ApiRequestError` (`status`, `code`, `message`, `requestId`); pages show `errorMessage(error)` and switch on
  `code` when needed. No per-feature error classes.
- **`login_required`** (any role) next to `roles_required`; the role areas in `frontend/src/core/routes.tsx` are
  built from one `ROLE_LAYOUTS` map, so a new role/area is one entry plus its layout.
- **Health:** a database outage logs one warning line (no traceback) and the landing badge says "API up,
  database unavailable" instead of "unreachable".
- **`GET /` on the API redirects to `/api/docs`** instead of a 404 JSON, since people open the API's root URL.

**Why:** a working login for all three roles is the base every later feature builds on; module-owned URLs keep
the "grep the module segment" rule without exceptions; the DB role check and 401-on-deactivation make an admin's
suspension take effect immediately; the manual mode is the simplest way to explain and demo the app.

## 2026-09-25: Node.js comes from the conda env

**What:** `environment.yml` installs `nodejs=22` (conda-forge) next to Python and Tesseract. Every node/npm command
runs through `conda run -n ca-helper` (Makefile `NPM` variable, pre-commit ESLint/Prettier hooks, `make setup`).
`.nvmrc` and all nvm instructions are removed. CI uses `actions/setup-node` with `node-version: "22"` (as it uses
pip, not conda, for Python) and the frontend Docker image stays on `node:22-alpine`. `package.json` `engines`
(`>=22.22`) with `engine-strict=true` remains the floor. Supersedes the `.nvmrc` point of the bootstrap entry.

**Why:** one tool (conda) now provides every runtime, so a fresh laptop needs only conda, Docker, git and make, and
everyone runs the same Node version without per-user nvm setups.

## 2026-09-25: JSON logs and request IDs

**What:** every request gets an ID: a valid incoming `X-Request-ID` (1–128 chars of `A-Za-z0-9._-`) is reused,
otherwise a UUID hex is generated (`app/core/request_id.py`). It is returned in the `X-Request-ID` header, added to
every log line and to every error body (`error.request_id`). The API logs one access line per request itself
(Werkzeug's and gunicorn's access lines are off). Logs are readable text by default and one JSON object per line
when `LOG_FORMAT=json` (set in docker-compose); the formatter is hand-written (`app/core/logging_config.py`), no
new dependency. gunicorn uses the same config (`backend/gunicorn.conf.py`). Worker log lines carry the job id in a
`job` field. `LOG_LEVEL` sets the level.

**Why:** a user or teammate can quote the request ID from an error and find every related log line; JSON lines
in Docker are searchable with `jq`, while text stays readable in a hybrid-mode terminal.

## 2026-09-25: Service-level transactions

**What:** routes parse input, call one service function and serialize the result; they never touch `db.session`.
Each public service function is one unit of work and commits once at its end; helpers composed by other service
functions do not commit and say so. Models hold data only. Tests wrap each test in one outer transaction with
SQLAlchemy 2.0 `join_transaction_mode="create_savepoint"`, so service commits only release savepoints and are
rolled back after the test. Flask-SQLAlchemy 3.1's `Session.get_bind()` ignores a session-level bind, so the
`database` fixture in `backend/conftest.py` (and only it) temporarily replaces `db.session` with a plain scoped
session bound to the test connection. This replaces the old "delete all rows after each test" cleanup.

**Why:** one obvious place where data is committed makes behaviour easy to reason about and explain; tests can
call real services (which commit) and still stay isolated and fast.

## 2026-09-25: mypy in lenient mode

**What:** `mypy==2.3.1` (dev dependency) runs in `make lint` and CI over `app`, `tests`, `worker.py` and
`conftest.py`. Lenient: only annotated functions are checked (`check_untyped_defs = false`) and missing third-party
stubs are ignored (`ignore_missing_imports = true`); config in `backend/pyproject.toml`. Where mypy cannot see
Flask-SQLAlchemy's runtime `db.Model`, `app/core/db/models.py` uses a `TYPE_CHECKING` alias to our `Base`.
The frontend already has TypeScript `"strict": true` (both tsconfigs).

**Why:** catches wrong types in the code we annotate without forcing annotations everywhere at once; it can be
tightened per module later.

## 2026-09-25: API routes under /api/v1

**What:** every module route is under `/api/v1/...`, added centrally by `register_blueprints()` (module blueprints
set no `url_prefix`). `/api/health`, `/api/docs` and `/api/openapi.json` stay unversioned for healthchecks and
tooling. The Vite proxy and nginx already forward all of `/api/`. The frontend client keeps `baseUrl: ""` because
the generated paths already contain `/api/v1`. Supersedes "No `/v1` in URLs" in the bootstrap conventions.

**Why:** a later breaking change can live at `/api/v2` next to v1 without moving the infrastructure endpoints that
Docker, CI and the status badge depend on.

## 2026-09-25: Enums stored as text with a CHECK constraint

**What:** Python `StrEnum`s with lowercase snake_case values, mapped with `str_enum()` (`app/core/db/enums.py`):
SQLAlchemy `Enum(native_enum=False, create_constraint=True, values_callable=values, validate_strings=True,
length=50)`. The database stores the value, never the member name, and a named CHECK constraint
(`ck_<table>_<enum>`) rejects anything else. The API sends the same codes; display labels live only in
`frontend/src/core/labels.ts` and the code → label tables in `docs/DATA_MODEL.md` ("Status values", rewritten
from display strings to codes: e.g. `docs_pending` → "Docs pending").

**Why:** Postgres ENUM types are awkward to change in migrations; text + CHECK gives the same safety with a
simple constraint swap, and stable machine codes keep display wording out of the database and API.

## 2026-09-25: UUID primary keys

**What:** every model subclasses `BaseModel` (`app/core/db/models.py`): `id` is a UUID (uuid4 generated in
Python, stored as Postgres `uuid`), plus `created_at`/`updated_at` (timezone-aware UTC, DB default `now()`).
`SoftDeleteMixin` (`is_active`, `deleted_at`) is opt-in for user-facing rows. The existing MetaData naming
convention (ix, uq, ck, fk, pk) stays, so Alembic gets stable constraint names.

**Why:** IDs in URLs cannot be guessed or counted (e.g. how many businesses exist), rows can be created in seeds
and tests without a DB round-trip for the key, and one base class gives every table the same key and timestamps.

## 2026-09-25: No in-repo ownership or task tracking

**What**
- Tasks are assigned and split among the team outside the repo. The repo no longer records who owns which
  module, which phase we are in, or which tasks are open.
- Removed: the ownership and phases docs, `docs/prompts/`, the `content` and `finish` module trackers, the progress
  tracker script (`scripts/progress.py`) with its tests, its three Make targets and the two CI steps that ran it,
  the import of each member's personal identity file in `CLAUDE.md`, and member letters, task IDs and owner fields
  in docs, `content/` front matter, `eval/` READMEs and code comments. `git log` has the exact files.
- Module docs have eight sections: Purpose · What exists now · Tables · Endpoints · Service functions other modules
  call · Depends on · Contracts (don't change without telling the team) · Known issues.
- Compliance item and engagement status values now live in `docs/DATA_MODEL.md` ("Status values"), their one
  authoritative home.
- Branches are named `<name>/<module>-<short-task>`. Anyone may change any file; a PR that touches `core/`, shared
  config or another module, or changes a contract, says so clearly.
- The frontend `ModulePlaceholder` no longer shows an owner or task IDs.
- Supersedes two points of the bootstrap entry below: CI no longer checks tracker lines, and ruff covers
  `backend/` only (no Python is left in `scripts/`).

**Why:** the team splits work in person, so an in-repo tracker and ownership rules were a second source of truth
to keep in sync. Everything technical (stack, rules, conventions, run modes) is unchanged.

## 2026-09-25: Initial bootstrap

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
- **Git history** starts with one empty root commit on `main` (the GitHub repo was empty), so the bootstrap can be a
  normal PR from `chore/phase-0-bootstrap`.
