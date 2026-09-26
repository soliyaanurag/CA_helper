# Decision log

Newest first. One entry per decision: date, what, why. Anything decided in chat that affects others goes here
in the same PR.

## 2026-09-26: Simplified for explainability

**What**
- **New rule in `CLAUDE.md`, "Simplicity first":** build the simplest thing that works and is explainable in 1–2
  sentences; no infrastructure, tooling or abstraction layers without asking.
- **Logging:** `logging.basicConfig` with `LOG_LEVEL` in `create_app()`. Gone: the JSON format and `LOG_FORMAT`,
  request IDs (`X-Request-ID`, `request_id` in error bodies, `requestId` in the frontend), the custom access log
  (the dev server's own request lines are back) and the worker's `job` log field (APScheduler logs each job by name).
- **Removed:** ProxyFix and `TRUST_PROXY`; full-Docker mode (both Dockerfiles and `.dockerignore`s, `nginx.conf`,
  gunicorn and `gunicorn.conf.py`, the worker heartbeat and `--healthcheck`, the CI docker job, `make up/down/logs`;
  `docker-compose.yml` keeps `db` and `mailpit`); mypy; pre-commit; flask-cors and `CORS_ORIGINS` (Vite forwards
  `/api`, so the browser talks to one origin); `ProductionConfig`; `DEV_SERVER_DEBUG` (`make dev-backend` now runs
  `python main.py`, like the manual mode); `RATELIMIT_STORAGE_URI` (fixed to `memory://`); every `.env` variable
  nothing read yet; `make test-backend` / `test-frontend` (`make test` runs both).
- **Tests:** the tables are created once per session and the `database` fixture deletes every row after each test,
  in reverse foreign-key order. No outer transaction, savepoints or `db.session` swap.
- **Dependencies: only what the code imports.** Python: removed pgvector, cryptography, google-genai, pytesseract,
  PyMuPDF, pdfplumber, opencv-python-headless, requests, beautifulsoup4, feedparser, gunicorn, Faker, mypy and
  pre-commit. Each feature adds its own packages when it lands; for PDFs that is PyMuPDF only (never pdfplumber as
  well, no OpenCV). `tesseract` left `environment.yml`, together with the Tesseract smoke test, the
  `requires_tesseract` marker and the CI install. npm: removed FullCalendar, recharts, lucide-react, openapi-fetch
  and `cn` (shadcn's clsx + tailwind-merge replacement); `lib/utils.js` is the standard shadcn `cn()` built on
  clsx + tailwind-merge, and `shadcn` is a devDependency. A calendar or chart library is chosen (ask first) when
  its page is built.
- **Frontend API client:** one `apiFetch(path, {method, body})` in `api/client.js` (adds the token, parses JSON,
  throws `ApiRequestError` with `code` and `message`, logs out on a 401) replaces openapi-fetch, `unwrap()` and the
  AuthProvider middleware. `lib/labels.js` keeps only the role labels.
- **Tooling and docs:** `scripts/setup_dev.sh` is ~50 lines (no conda → print the Miniforge command and stop;
  otherwise env, `npm ci`, `.conda-env` link, `.env` with random secrets). `docs/WORKFLOW.md` is merged into
  `CLAUDE.md`. `docs/PATTERNS.md` covers only patterns with code behind them.
- **Unchanged:** every endpoint and response (except the dropped `request_id`), error code, table, migration and
  the login flow.

**Why:** every file must be explainable in the viva by a team of three. Most of what went served a deployment we
do not run (Docker images, nginx, gunicorn, proxy headers, JSON logs) or features that do not exist yet (their
packages and settings); the rest (mypy, pre-commit, the openapi-fetch middleware, the savepoint fixture) needed
long explanations for little benefit at this size.

**Supersedes:** "JSON logs and request IDs" and "mypy in lenient mode" (2026-09-25); the savepoint fixture in
"Service-level transactions"; openapi-fetch in "Frontend in plain JavaScript"; the `api.use()` middleware,
`unwrap()` and `DEV_SERVER_DEBUG` in "Basic login, role areas and manual run mode"; the pre-commit hooks and the
frontend Docker image in "Node.js comes from the conda env"; FullCalendar, nginx, `cn`, pre-commit, port 8080, the
Tesseract CI step and the CI docker job in "Initial bootstrap".

## 2026-09-26: Frontend in plain JavaScript, not TypeScript

> **Partly superseded (2026-09-26, "Simplified for explainability"):** openapi-fetch is gone; calls use `apiFetch()`.

**What**
- Every frontend file is `.js` / `.jsx` (types stripped mechanically, comments kept). `tsconfig*.json` is replaced
  by a small `jsconfig.json` (editor support for the `@/` alias only); shadcn `components.json` has `"tsx": false`.
- Removed: `typescript`, `typescript-eslint`, `@types/*`, `openapi-typescript`, the `typecheck` and `gen:api` npm
  scripts, `make gen-api`, `src/api/generated/`, and the CI/Docker steps that generated or checked types. The
  frontend CI job no longer waits for the backend job.
- Kept: **openapi-fetch** as the API client (same `api.GET("/api/v1/...")` calls, now untyped), `unwrap()`,
  Zod for form validation. Swagger at `/api/docs` is the reference for request/response fields. CI still checks
  that the OpenAPI spec builds.

**Why**
- All three team members know JavaScript/JSX but not TypeScript; the code has to be explainable in the viva.
  TypeScript was generated by mistake.
- Trade-off accepted: a renamed backend field is no longer caught at build time, only by tests or at runtime.
  Keep every API call in `api/<module>.js` so a schema change means checking one place.
- Supersedes "TypeScript 5.9", "openapi-fetch: typed client" and "Generated API types are not committed" in the
  2026-09-25 entry; `.ts`/`.tsx` paths in older entries now end in `.js`/`.jsx`.

## 2026-09-26: Folders by layer instead of by module; explicit registration

**What**
- **Backend `app/` is organised by layer:** `models/`, `schemas/`, `services/` (`<module>_service.py`),
  `routes/`, `utils/`, plus `config.py`, `extensions.py`, `errors.py`, `seed.py` at the top. All tests are in
  `backend/tests/` with `tests/conftest.py`. A module is the set of same-named files across the layers. Files are
  created only when they have code (the empty per-module stubs are gone).
- **Frontend `src/` is organised by layer:** `api/`, `pages/` (`business/`, `ca/`, `admin/`), `components/`,
  `context/`, `hooks/`, `lib/`, and one route table `src/routes.jsx`.
- **Registration is explicit, no auto-discovery:** `BLUEPRINTS` in `app/routes/__init__.py`, every model imported
  in `app/models/__init__.py`, `SEEDS` in `app/seed.py`, jobs in `build_scheduler()` (`worker.py`), pages and
  sidebar links (`NAV`) in `src/routes.jsx`. Supersedes "Module auto-discovery" and "Frontend route aggregation"
  (bootstrap entry) and `ROLE_LAYOUTS` / `AREA_PREFIX` (login entry).
- **Merged small files:** `cli.py` into `seed.py`; `request_id.py` into `utils/logging_setup.py`; `core/db/base.py`
  (`Base`, naming convention) into `extensions.py`; `core/api/errors.ts` into `api/client.js`; the three role
  layouts into `AppShell` (takes the role); `AreaIndexPage` removed (every area has a dashboard).
  `issue_access_token()` moved from `tokens.py` to `services/auth_service.py`; the heartbeat job id is now
  `worker.heartbeat`; `flask seed` prints `Seeded: demo users`.
- **Unchanged:** every URL, response, error code, table, migration, env variable, Make target, Docker and CI
  step, and all behaviour (request IDs, JSON logs, ProxyFix, heartbeat). `flask db check` reports no schema change.

Older entries below name files by their old paths. Old → new:

| Old | New |
|---|---|
| `app/core/auth/{models,routes,schemas,services}.py` | `app/models/user.py`, `app/routes/auth.py`, `app/schemas/auth.py`, `app/services/auth_service.py` |
| `app/core/auth/tokens.py`, `app/core/auth/seed.py`, `app/cli.py` | `app/utils/jwt_handlers.py`, `app/seed.py` |
| `app/core/permissions.py`, `app/core/security/passwords.py` | `app/utils/decorators.py`, `app/utils/passwords.py` |
| `app/core/db/{base,models,enums}.py` | `app/extensions.py` (`Base`), `app/models/base.py`, `app/models/enums.py` |
| `app/core/{errors,health}.py` | `app/errors.py`, `app/routes/health.py` |
| `app/core/{logging_config,request_id}.py` | `app/utils/logging_setup.py` |
| `app/modules/<m>/{routes,schemas,services}.py`, `.../tests/` | `app/routes/<m>.py`, `app/schemas/<m>.py`, `app/services/<m>_service.py`, `tests/test_<m>_*.py` |
| `app/core/{ai,ocr,storage,...}` (planned) | `app/utils/{gemini_client,ocr,storage,...}.py` (planned) |
| `backend/conftest.py` | `backend/tests/conftest.py` |
| `frontend/src/core/api/`, `core/auth/`, `core/layout/`, `core/components/` | `src/api/`, `src/context/` + `src/hooks/` + `src/lib/session.js`, `src/components/` |
| `frontend/src/core/{routes.tsx,labels.ts,query-client.ts}` | `src/routes.jsx`, `src/lib/labels.js`, `src/lib/queryClient.js` |
| `frontend/src/features/<m>/{pages,api.ts,routes.tsx}` | `src/pages/<role>/`, `src/api/<m>.js`, entries in `src/routes.jsx` |

**Why:** the per-module folders held mostly empty placeholder files, and auto-discovery hid which routes and pages
exist. The layer-first layout is the one most Flask and React tutorials use, so each file is easy to find and to
explain in the viva. One file per module per layer keeps the modules separate.

## 2026-09-25: Basic login, role areas and manual run mode

> **Partly superseded (2026-09-26, "Simplified for explainability"):** `apiFetch()` replaces `unwrap()` and the middleware; `make dev-backend` runs `python main.py`, so `DEV_SERVER_DEBUG` is gone.

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

> **Partly superseded (2026-09-26, "Simplified for explainability"):** there are no pre-commit hooks or Docker images any more.

**What:** `environment.yml` installs `nodejs=22` (conda-forge) next to Python and Tesseract. Every node/npm command
runs through `conda run -n ca-helper` (Makefile `NPM` variable, pre-commit ESLint/Prettier hooks, `make setup`).
`.nvmrc` and all nvm instructions are removed. CI uses `actions/setup-node` with `node-version: "22"` (as it uses
pip, not conda, for Python) and the frontend Docker image stays on `node:22-alpine`. `package.json` `engines`
(`>=22.22`) with `engine-strict=true` remains the floor. Supersedes the `.nvmrc` point of the bootstrap entry.

**Why:** one tool (conda) now provides every runtime, so a fresh laptop needs only conda, Docker, git and make, and
everyone runs the same Node version without per-user nvm setups.

## 2026-09-25: JSON logs and request IDs

> **Superseded (2026-09-26, "Simplified for explainability"):** plain `logging.basicConfig`, no request IDs.

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

> **Partly superseded (2026-09-26, "Simplified for explainability"):** services still commit once; tests now delete every row after each test instead of rolling back a savepoint transaction.

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

> **Superseded (2026-09-26, "Simplified for explainability"):** mypy is removed.

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
- Branches are named `<name>/<module>-<short-task>`. Anyone may change any file; a PR that touches shared code, shared
  config or another module, or changes a contract, says so clearly.
- The frontend `ModulePlaceholder` no longer shows an owner or task IDs.
- Supersedes two points of the bootstrap entry below: CI no longer checks tracker lines, and ruff covers
  `backend/` only (no Python is left in `scripts/`).

**Why:** the team splits work in person, so an in-repo tracker and ownership rules were a second source of truth
to keep in sync. Everything technical (stack, rules, conventions, run modes) is unchanged.

## 2026-09-25: Initial bootstrap

> **Partly superseded (2026-09-26, "Simplified for explainability"):** no full-Docker mode (nginx, gunicorn, port 8080, CI docker job), pre-commit, `cn`, FullCalendar or Tesseract CI step.

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
