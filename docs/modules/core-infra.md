# core-infra: shared backend infrastructure, worker and dev environment

## Purpose
The foundation every module builds on: the dev environment (conda, Makefile, Postgres + Mailpit in Docker, CI), the Flask app factory and blueprint registration, the JSON error format, OpenAPI docs, the model base classes, and the shared helpers in `backend/app/utils/` (later also encryption, storage, email, notifications, the Gemini wrapper and OCR), plus `backend/worker.py`.

## What exists now
Code: `backend/app/__init__.py`, `config.py`, `extensions.py`, `errors.py`, `seed.py`, `models/base.py`, `models/enums.py`, `routes/__init__.py`, `routes/health.py`, `backend/main.py`, `backend/worker.py`, `backend/tests/conftest.py`, `backend/migrations/`, root configs, `scripts/setup_dev.sh`, `.github/`.
- **Works:** app factory with development/testing config (reads the root `.env`; `APP_ENV` picks one); plain logging (`logging.basicConfig`, level from `LOG_LEVEL`); extensions (SQLAlchemy, Migrate, JWT, Limiter with in-memory counters, flask-smorest); `register_routes()` registering `/api/health` and every blueprint in `BLUEPRINTS` under `/api/v1` (`API_PREFIX`, `routes/__init__.py`); `flask seed` (runs every function in `SEEDS`, `seed.py`); the JSON error format (`CaHelperApi`, `ApiError`); `GET /api/health`; OpenAPI spec + Swagger UI; `GET /` redirects to `/api/docs`; declarative `Base` with a constraint naming convention (`extensions.py`); `BaseModel` (UUID `id`), `TimestampMixin`, `SoftDeleteMixin`, `utcnow()` (`models/base.py`); `str_enum()` for StrEnum columns stored as text + CHECK (`models/enums.py`); Alembic migrations (core-auth `users`, `email_otps`); email: `send_email(to, subject, template, **context)` in `app/utils/email.py` sends a plain-text email rendered from `app/templates/email/<template>.txt` (Jinja, via Flask's `render_template`) with the standard library's `smtplib` to `MAIL_SERVER`/`MAIL_PORT` (Mailpit in development); a failure is logged without the address and returns False instead of raising; with `MAIL_SUPPRESS_SEND` (tests) messages go to the `outbox` list instead; dev server `backend/main.py` (debugger + auto-reload on 127.0.0.1:8000, run by `make dev-backend`); worker (`AppScheduler`: Asia/Kolkata cron, every job runs in the app context; APScheduler logs each job by name); feature jobs are added in `build_scheduler()` (none yet).
- **Not built yet** (planned files, listed in `app/utils/__init__.py`): `utils/encryption.py`, `utils/storage.py`, notifications, `utils/gemini_client.py`, `utils/ocr.py`; no money helpers yet. Their packages (cryptography, google-genai, pytesseract, PyMuPDF, ...) and `.env` variables are added with them.
- **Tests:** backend tests in `backend/tests/`: app factory and error format (including the 500 body), `/api/v1` prefix (checked on the real app's URL rules), health, seed command, worker (jobs run in the app context), base model/mixins/enums and per-test cleanup (`test_db_foundations.py`, with the test-only model in `tests/_models.py`), email (`test_email.py`: template, outbox, SMTP hand-off, failure logged without the address). Shared fixtures in `backend/tests/conftest.py` create the test database and its tables once per session and delete every row after each test (reverse foreign-key order); the autouse `mailbox` fixture empties the email outbox before each test.
- **Dev environment:** conda env `ca-helper` (Python 3.12, Node 22, pip packages from `backend/requirements*.txt`) + `make setup`; `docker-compose.yml` with `db` (Postgres 16 + pgvector image, healthcheck) and `mailpit`, started by `make infra`; Makefile (all Python and npm commands via `conda run`; `make help` lists the targets); team workflow targets `make doctor`, `feature`, `sync`, `check`, `pr`, `merge` in `scripts/workflow.sh` (README "Team workflow"); CI with a backend job (ruff, migrations, pytest with Postgres, OpenAPI spec builds) and a frontend job (lint, format, tests, build).

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
- `app.utils.passwords.hash_password()/verify_password()` (exist)
- `app.utils.email.send_email(to, subject, template, **context) -> bool` (exists): add the body as `backend/app/templates/email/<template>.txt`; call it after the commit, since a failed send never raises
- Planned: `EncryptedString`, `blind_index()`; `storage.save_file()/load_file()`; `notify()`; `gemini_client.generate()/embed()`; OCR helpers

## Depends on
Nothing (this is the base layer).

## Contracts (don't change without telling the team)
- Error body: `{"error": {"code", "message", "details?"}}` (see docs/API_CONVENTIONS.md)
- Module routes are under `/api/v1`; `/api/health`, `/api/docs`, `/api/openapi.json` stay unversioned
- Every model subclasses `BaseModel` (UUID `id`, UTC `created_at`/`updated_at`); enums use `str_enum()` (lowercase snake_case codes)
- Each public service function commits once at its end; routes never touch `db.session`
- A module's blueprint sets no `url_prefix` and is listed in `BLUEPRINTS`; its models are imported in `models/__init__.py`; its seed function is listed in `SEEDS`; its jobs are added in `worker.py`
- Jobs run inside the Flask app context; cron times are Asia/Kolkata; give every job a unique `id` like `alerts.due_reminders`
- Every Gemini call goes through `app/utils/gemini_client.py` (rule 1)

## Known issues
- Rate-limit counters live in memory (`memory://`), per process: they reset when the API restarts. Fine for a single dev server.
- `send_email()` speaks plain SMTP without TLS or login, which is enough for Mailpit. A real mail server would need `MAIL_USE_TLS`, `MAIL_USERNAME` and `MAIL_PASSWORD` (not added yet).
