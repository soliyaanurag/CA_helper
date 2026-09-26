# core-infra: shared backend infrastructure, worker and dev environment

## Purpose
The foundation every module builds on: the dev environment (conda, Docker, Makefile, CI), the Flask app factory and blueprint registration, the JSON error format, OpenAPI docs, the model base classes, and the shared helpers in `backend/app/utils/` (logging, and later encryption, storage, email, notifications, the Gemini wrapper and OCR), plus `backend/worker.py`.

## What exists now
Code: `backend/app/__init__.py`, `config.py`, `extensions.py`, `errors.py`, `seed.py`, `models/base.py`, `models/enums.py`, `routes/__init__.py`, `routes/health.py`, `utils/logging_setup.py`, `backend/worker.py`, `backend/gunicorn.conf.py`, `backend/tests/conftest.py`, `backend/migrations/`, root configs, `scripts/setup_dev.sh`, `.github/`.
- **Works:** app factory with development/testing/production config (reads the root `.env`); extensions (SQLAlchemy, Migrate, JWT, CORS, Limiter, flask-smorest); `register_routes()` registering `/api/health` and every blueprint in `BLUEPRINTS` under `/api/v1` (`API_PREFIX`, `routes/__init__.py`); `flask seed` (runs every function in `SEEDS`, `seed.py`); the JSON error format (`CaHelperApi`, `ApiError`); `GET /api/health`; OpenAPI spec + Swagger UI; declarative `Base` with a constraint naming convention (`extensions.py`); `BaseModel` (UUID `id`), `TimestampMixin`, `SoftDeleteMixin`, `utcnow()` (`models/base.py`); `str_enum()` for StrEnum columns stored as text + CHECK (`models/enums.py`); request IDs (`X-Request-ID` in, out, in logs and error bodies), one access log line per request, and text/JSON logging with `request_id` and `job` on every line (`utils/logging_setup.py`, also used by gunicorn via `gunicorn.conf.py`); ProxyFix when `TRUST_PROXY=1`; Alembic set up with **no migrations yet**; worker (`AppScheduler`: Asia/Kolkata cron, every job in the app context with its id in the logs, built-in `worker.heartbeat` job, `python worker.py --healthcheck`); feature jobs are added in `build_scheduler()` (none yet).
- **Not built yet** (planned files, listed in `app/utils/__init__.py`): `utils/encryption.py`, `utils/storage.py`, `utils/email.py`, notifications, `utils/gemini_client.py`, `utils/ocr.py`; no money helpers yet.
- **Tests:** backend tests in `backend/tests/`: app factory and error format, health, seed command, worker (app context, job names in logs, heartbeat), Tesseract smoke test, base model/mixins/enums and per-test savepoint rollback (`test_db_foundations.py`, with the test-only model in `tests/_models.py`), request IDs and log formats, `/api/v1` prefix and ProxyFix. Shared fixtures in `backend/tests/conftest.py` create the test database and wrap each test in a rolled-back transaction.
- **Dev environment:** conda env `ca-helper` (Python, Tesseract, Node 22) + `make setup`; Docker Compose with 5 services (db, mailpit, backend, worker, frontend), each with a healthcheck; Makefile (all Python and npm commands via `conda run`); pre-commit hooks; mypy (lenient) in `make lint`; CI with backend (ruff, mypy, migrations, pytest), frontend and Docker jobs (all 5 services healthy + smoke test).

## Tables
None yet. Planned:
- `notifications`: in-app tray entries per user

## Endpoints
- `GET /api/health`: API + database status (exists)
- `GET /api/openapi.json`, `GET /api/docs`: OpenAPI spec and Swagger UI (exist)
- Planned: notification tray API under `/api/v1/notifications/...`

## Service functions other modules call
- `app.errors.ApiError(status, code, message, details=None)`: raise for expected errors (exists)
- `app.routes.BLUEPRINTS` / `register_routes()` / `API_PREFIX`, `app.seed.SEEDS` / `run_all_seeds()` (exist)
- `app.models.base.BaseModel`, `TimestampMixin`, `SoftDeleteMixin`, `utcnow()` (exist)
- `app.models.enums.str_enum(EnumCls, name=None)` (exists)
- `app.utils.logging_setup.get_request_id()` (exists)
- `app.utils.passwords.hash_password()/verify_password()` (exist)
- Planned: `EncryptedString`, `blind_index()`; `storage.save_file()/load_file()`; `send_email()` and `notify()`; `gemini_client.generate()/embed()`; OCR helpers

## Depends on
Nothing (this is the base layer).

## Contracts (don't change without telling the team)
- Error body: `{"error": {"code", "message", "details?", "request_id"}}` and the `X-Request-ID` header (see docs/API_CONVENTIONS.md)
- Module routes are under `/api/v1`; `/api/health`, `/api/docs`, `/api/openapi.json` stay unversioned
- Every model subclasses `BaseModel` (UUID `id`, UTC `created_at`/`updated_at`); enums use `str_enum()` (lowercase snake_case codes)
- Each public service function commits once at its end; routes never touch `db.session`
- A module's blueprint sets no `url_prefix` and is listed in `BLUEPRINTS`; its models are imported in `models/__init__.py`; its seed function is listed in `SEEDS`; its jobs are added in `worker.py`
- Jobs run inside the Flask app context; cron times are Asia/Kolkata; give every job a unique `id` like `alerts.due_reminders`
- Every Gemini call goes through `app/utils/gemini_client.py` (rule 1)

## Known issues
- The CI workflow (`.github/workflows/ci.yml`) has not run on GitHub yet; its first run is on the bootstrap PR.
  Every step was verified locally with the same commands.
- `TRUST_PROXY=1` (Docker) trusts one proxy's `X-Forwarded-*` headers. The backend also publishes port 8000 directly, so in Docker a client that bypasses nginx could spoof its IP for rate limiting; fine for dev, but a deployment must expose only nginx.
- The two Alembic lines printed by `flask db upgrade` at backend container start are plain text, not JSON: `migrations/env.py` (kept as generated) configures its own logging from `alembic.ini`.
- `RATELIMIT_STORAGE_URI=memory://` counts per gunicorn worker process; fine for dev.
