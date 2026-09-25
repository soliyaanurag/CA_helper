# core-infra: shared backend infrastructure, worker and dev environment

## Purpose
The foundation every module builds on: the dev environment (conda, Docker, Makefile, CI), the Flask app factory and module auto-discovery, the JSON error format, OpenAPI docs, and the shared services in `backend/app/core/`: db, security (encryption), storage, email, notifications, ai (Gemini wrapper), ocr, plus `backend/worker.py`.

## What exists now
Code: `backend/app/__init__.py`, `config.py`, `extensions.py`, `cli.py`, `backend/app/core/`, `backend/app/modules/__init__.py`, `backend/worker.py`, `backend/gunicorn.conf.py`, `backend/conftest.py`, `backend/migrations/`, root configs, `scripts/setup_dev.sh`, `.github/`.
- **Works:** app factory with development/testing/production config (reads the root `.env`); extensions (SQLAlchemy, Migrate, JWT, CORS, Limiter, flask-smorest); module auto-discovery registering all 9 module blueprints under `/api/v1` (`API_PREFIX`); `flask seed` (runs every module's `seed()`); the JSON error format (`CaHelperApi`, `ApiError`); `GET /api/health`; OpenAPI spec + Swagger UI; declarative `Base` with a constraint naming convention (`core/db/base.py`); `BaseModel` (UUID `id`), `TimestampMixin`, `SoftDeleteMixin`, `utcnow()` (`core/db/models.py`); `str_enum()` for StrEnum columns stored as text + CHECK (`core/db/enums.py`); request IDs (`X-Request-ID` in, out, in logs and error bodies) and one access log line per request (`core/request_id.py`); text/JSON logging with `request_id` and `job` on every line (`core/logging_config.py`, also used by gunicorn via `gunicorn.conf.py`); ProxyFix when `TRUST_PROXY=1`; Alembic set up with **no migrations yet**; worker (`AppScheduler`: Asia/Kolkata cron, every job in the app context with its id in the logs, built-in `core.heartbeat` job, `python worker.py --healthcheck`) that collects `register_jobs` from modules (none define it yet).
- **Empty packages (docstring only):** `core/security`, `core/storage`, `core/email`, `core/notifications`, `core/ai`, `core/ocr`; no money helpers yet.
- **Tests:** 47 backend tests in `backend/tests/`: app factory and error format, health, seed command, worker (app context, job names in logs, heartbeat), Tesseract smoke test, base model/mixins/enums and per-test savepoint rollback (`test_db_foundations.py`, with the test-only model in `tests/_models.py`), request IDs and log formats, `/api/v1` prefix and ProxyFix. Shared fixtures in `backend/conftest.py` create the test database and wrap each test in a rolled-back transaction.
- **Dev environment:** conda env `ca-helper` (Python, Tesseract, Node 22) + `make setup`; Docker Compose with 5 services (db, mailpit, backend, worker, frontend), each with a healthcheck; Makefile (all Python and npm commands via `conda run`); pre-commit hooks; mypy (lenient) in `make lint`; CI with backend (ruff, mypy, migrations, pytest), frontend and Docker jobs (all 5 services healthy + smoke test).

## Tables
None yet. Planned:
- `notifications`: in-app tray entries per user

## Endpoints
- `GET /api/health`: API + database status (exists)
- `GET /api/openapi.json`, `GET /api/docs`: OpenAPI spec and Swagger UI (exist)
- Planned: notification tray API under `/api/v1/notifications/...`

## Service functions other modules call
- `app.core.errors.ApiError(status, code, message, details=None)`: raise for expected errors (exists)
- `app.modules.discover_modules() / register_all_jobs() / run_all_seeds()`, `API_PREFIX` (exist)
- `app.core.db.models.BaseModel`, `TimestampMixin`, `SoftDeleteMixin`, `utcnow()` (exist)
- `app.core.db.enums.str_enum(EnumCls, name=None)` (exists)
- `app.core.request_id.get_request_id()` (exists)
- Planned: `EncryptedString`, `blind_index()`, `hash_password()/verify_password()`; `storage.save_file()/load_file()`; `send_email()` and `notify()`; `gemini_client.generate()/embed()`; OCR helpers

## Depends on
Nothing (this is the base layer).

## Contracts (don't change without telling the team)
- Error body: `{"error": {"code", "message", "details?", "request_id"}}` and the `X-Request-ID` header (see docs/API_CONVENTIONS.md)
- Module routes are under `/api/v1`; `/api/health`, `/api/docs`, `/api/openapi.json` stay unversioned
- Every model subclasses `BaseModel` (UUID `id`, UTC `created_at`/`updated_at`); enums use `str_enum()` (lowercase snake_case codes)
- Each public service function commits once at its end; routes never touch `db.session`
- A module package exposes `blp` (no `url_prefix`), optional `seed()`, `SEED_ORDER`, `register_jobs(scheduler)`
- Jobs run inside the Flask app context; cron times are Asia/Kolkata; give every job a unique `id` like `alerts.due_reminders`
- Every Gemini call goes through `app/core/ai/gemini_client.py` (rule 1)

## Known issues
- The CI workflow (`.github/workflows/ci.yml`) has not run on GitHub yet; its first run is on the bootstrap PR.
  Every step was verified locally with the same commands.
- `TRUST_PROXY=1` (Docker) trusts one proxy's `X-Forwarded-*` headers. The backend also publishes port 8000 directly, so in Docker a client that bypasses nginx could spoof its IP for rate limiting; fine for dev, but a deployment must expose only nginx.
- The two Alembic lines printed by `flask db upgrade` at backend container start are plain text, not JSON: `migrations/env.py` (kept as generated) configures its own logging from `alembic.ini`.
- `RATELIMIT_STORAGE_URI=memory://` counts per gunicorn worker process; fine for dev.
