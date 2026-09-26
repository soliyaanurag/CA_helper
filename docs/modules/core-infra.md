# core-infra: shared backend infrastructure, worker and dev environment

## Purpose
The foundation every module builds on: the dev environment (conda, Docker for Postgres + Mailpit, Makefile, CI), the Flask app factory and module auto-discovery, the JSON error format, OpenAPI docs, and the shared services in `backend/app/core/`: db, security (encryption), storage, email, notifications, ai (Gemini wrapper), ocr, plus `backend/worker.py`.

## What exists now
Code: `backend/app/__init__.py`, `config.py`, `extensions.py`, `cli.py`, `backend/app/core/`, `backend/app/modules/__init__.py`, `backend/worker.py`, `backend/main.py`, `backend/conftest.py`, `backend/migrations/`, root configs, `scripts/setup_dev.sh`, `.github/`.
- **Works:** app factory with development/testing config (reads the root `.env`); plain console logging (`logging.basicConfig`, level from `LOG_LEVEL`); extensions (SQLAlchemy, Migrate, JWT, CORS, Limiter, flask-smorest); module auto-discovery registering all 9 module blueprints under `/api/v1` (`API_PREFIX`); `flask seed` (demo users, then every module's `seed()` by name, one commit); the JSON error format (`CaHelperApi`, `ApiError`); `GET /api/health`; OpenAPI spec + Swagger UI; `GET /` redirects to `/api/docs`; declarative `Base` with a constraint naming convention (`core/db/base.py`); `BaseModel` (UUID `id`), `TimestampMixin`, `SoftDeleteMixin`, `utcnow()` (`core/db/models.py`); `str_enum()` for StrEnum columns stored as text + CHECK (`core/db/enums.py`); Alembic with one migration (`users`); worker (`AppScheduler`: Asia/Kolkata cron, every job runs in the app context) that collects `register_jobs` from modules (none define it yet); `main.py` for the manual dev server.
- **Empty packages (docstring only):** `core/storage`, `core/email`, `core/notifications`, `core/ai`, `core/ocr`; `core/security` has only password hashing. Their dependencies (cryptography, google-genai, pytesseract, PyMuPDF, ...) are added with the feature that builds them.
- **Tests:** backend tests in `backend/tests/`: app factory and error format, `/api/v1` prefix, health, seed command, worker (jobs run in the app context), base model/mixins/enums and per-test cleanup (`test_db_foundations.py`, with the test-only model in `tests/_models.py`), auth. Shared fixtures in `backend/conftest.py`: the test database and its tables are created once per session, and after each test that uses `database` every row is deleted.
- **Dev environment:** conda env `ca-helper` (Python, Tesseract, Node 22) + `make setup`; Docker Compose with only `db` (Postgres 16, pgvector image) and `mailpit`; Makefile (all Python and npm commands via `conda run`); `make lint` = ruff + ESLint + Prettier + tsc; CI with a backend job (ruff, migrations, pytest, OpenAPI export) and a frontend job (types, lint, format, typecheck, tests, build).

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
- `app.core.security.passwords.hash_password()/verify_password()` (exist)
- Planned: `EncryptedString`, `blind_index()`; `storage.save_file()/load_file()`; `send_email()` and `notify()`; `gemini_client.generate()/embed()`; OCR helpers

## Depends on
Nothing (this is the base layer).

## Contracts (don't change without telling the team)
- Error body: `{"error": {"code", "message", "details?"}}` (see docs/API_CONVENTIONS.md)
- Module routes are under `/api/v1`; `/api/health`, `/api/docs`, `/api/openapi.json` stay unversioned
- Every model subclasses `BaseModel` (UUID `id`, UTC `created_at`/`updated_at`); enums use `str_enum()` (lowercase snake_case codes)
- Each public service function commits once at its end; routes never touch `db.session`
- A module package exposes `blp` (no `url_prefix`), optional `seed()` and `register_jobs(scheduler)`
- Jobs run inside the Flask app context; cron times are Asia/Kolkata; give every job a unique `id` like `alerts.due_reminders`
- Every Gemini call goes through `app/core/ai/gemini_client.py` (rule 1)

## Known issues
- `RATELIMIT_STORAGE_URI=memory://` counts per process; fine for the dev server.
- There is no production setup (no Dockerfiles, no WSGI server config); it gets designed if the project is deployed.
