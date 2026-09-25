# core-infra: shared backend infrastructure, worker and dev environment

## Purpose
The foundation every module builds on: the dev environment (conda, Docker, Makefile, CI), the Flask app factory and module auto-discovery, the JSON error format, OpenAPI docs, and the shared services in `backend/app/core/`: db, security (encryption), storage, email, notifications, ai (Gemini wrapper), ocr, plus `backend/worker.py`.

## What exists now
Code: `backend/app/__init__.py`, `config.py`, `extensions.py`, `cli.py`, `backend/app/core/`, `backend/app/modules/__init__.py`, `backend/worker.py`, `backend/conftest.py`, `backend/migrations/`, root configs, `scripts/setup_dev.sh`, `.github/`.
- **Works:** app factory with development/testing/production config (reads the root `.env`); extensions (SQLAlchemy, Migrate, JWT, CORS, Limiter, flask-smorest); module auto-discovery registering all 9 module blueprints; `flask seed` (runs every module's `seed()`); the JSON error format (`CaHelperApi`, `ApiError`); `GET /api/health`; OpenAPI spec + Swagger UI; declarative `Base` with a constraint naming convention (`core/db/base.py`); Alembic set up with **no migrations yet**; worker (`AppScheduler`: Asia/Kolkata cron, every job in the app context) that collects `register_jobs` from modules (none define it yet).
- **Empty packages (docstring only):** `core/security`, `core/storage`, `core/email`, `core/notifications`, `core/ai`, `core/ocr`; no db mixins or money helpers yet.
- **Tests:** 11 backend tests in `backend/tests/` (app factory and error format, health, seed command, worker, Tesseract smoke test); shared fixtures in `backend/conftest.py` create the test database.
- **Dev environment:** conda env `ca-helper` + `make setup`, Docker Compose with 5 services (db, mailpit, backend, worker, frontend), Makefile, pre-commit hooks, CI with backend, frontend and Docker jobs.

## Tables
None yet. Planned:
- `notifications`: in-app tray entries per user

## Endpoints
- `GET /api/health`: API + database status (exists)
- `GET /api/openapi.json`, `GET /api/docs`: OpenAPI spec and Swagger UI (exist)
- Planned: notification tray API under `/api/notifications/...`

## Service functions other modules call
- `app.core.errors.ApiError(status, code, message, details=None)`: raise for expected errors (exists)
- `app.modules.discover_modules() / register_all_jobs() / run_all_seeds()` (exist)
- Planned: `EncryptedString`, `blind_index()`, `hash_password()/verify_password()`; `storage.save_file()/load_file()`; `send_email()` and `notify()`; `gemini_client.generate()/embed()`; OCR helpers

## Depends on
Nothing (this is the base layer).

## Contracts (don't change without telling the team)
- Error body: `{"error": {"code", "message", "details?"}}` (see docs/API_CONVENTIONS.md)
- A module package exposes `blp`, optional `seed()`, `SEED_ORDER`, `register_jobs(scheduler)`
- Jobs run inside the Flask app context; cron times are Asia/Kolkata; give every job a unique `id` like `alerts.due_reminders`
- Every Gemini call goes through `app/core/ai/gemini_client.py` (rule 1)

## Known issues
- The CI workflow (`.github/workflows/ci.yml`) has not run on GitHub yet; its first run is on the bootstrap PR.
  Every step was verified locally with the same commands.
- Flask-Limiter uses the client IP. Behind nginx (full-Docker/production) every request shows nginx's IP until `ProxyFix` is configured (do this together with login rate limiting or the production deployment).
- `RATELIMIT_STORAGE_URI=memory://` counts per gunicorn worker process; fine for dev.
