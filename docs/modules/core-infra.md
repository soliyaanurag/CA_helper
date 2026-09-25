# core-infra: shared backend infrastructure, worker and dev environment

## Purpose
The foundation every module builds on: the dev environment (conda, Docker, Makefile, CI), the Flask app factory and module auto-discovery, the JSON error format, OpenAPI docs, and the shared services in `backend/app/core/`: db, security (encryption), storage, email, notifications, ai (Gemini wrapper), ocr, plus `backend/worker.py`.

## Owner
Member B (Infrastructure, documents & AI)

Folders: `backend/app/__init__.py`, `config.py`, `extensions.py`, `cli.py`, `backend/app/core/{db,security,storage,email,notifications,ai,ocr}/`, `backend/app/core/errors.py`, `backend/app/core/health.py`, `backend/app/modules/__init__.py`, `backend/worker.py`, `backend/conftest.py`, `backend/migrations/`, root configs, `scripts/`, `.github/`

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [x] INF-01 · P0 · B · Conda env, setup script, Docker infra, Makefile, CI, pre-commit
- [x] INF-02 · P0 · B · Flask app factory, module auto-discovery, error format, OpenAPI docs, health endpoint
- [x] INF-03 · P0 · B · CLAUDE.md, docs, module docs, progress tracker script
- [ ] INF-04 · P1 · B · EncryptedString + blind index + encrypted file storage
- [ ] INF-05 · P1 · B · Email service (Mailpit in dev) + notification model + tray API
- [ ] INF-06 · P1 · B · Worker process + per-module job registration
- [ ] INF-07 · P1 · B · Gemini client wrapper with PII scrub
- [ ] INF-08 · P2 · B · OCR utility (Tesseract/PyMuPDF) + requires_tesseract tests
- [ ] INF-09 · P5 · B · Production deployment configuration

## Tables owned
- `notifications` (INF-05, planned): in-app tray entries per user
- Base class with naming convention: `app/core/db/base.py` (exists)

## Endpoints exposed
- `GET /api/health`: API + database status (exists)
- `GET /api/openapi.json`, `GET /api/docs`: OpenAPI spec and Swagger UI (exist)
- Notification tray API under `/api/notifications/...` (INF-05, planned)

## Service functions others may call
- `app.core.errors.ApiError(status, code, message, details=None)`: raise for expected errors (exists)
- `app.modules.discover_modules() / register_all_jobs() / run_all_seeds()` (exist)
- Planned: `EncryptedString`, `blind_index()`, `hash_password()/verify_password()` (INF-04); `storage.save_file()/load_file()` (INF-04); `send_email()` and `notify()` (INF-05); `gemini_client.generate()/embed()` (INF-07); OCR helpers (INF-08)

## Depends on
Nothing (this is the base layer).

## Contracts others rely on
- Error body: `{"error": {"code", "message", "details?"}}` (see docs/API_CONVENTIONS.md)
- A module package exposes `blp`, optional `seed()`, `SEED_ORDER`, `register_jobs(scheduler)`
- Jobs run inside the Flask app context; cron times are Asia/Kolkata; give every job a unique `id` like `alerts.due_reminders`
- Every Gemini call goes through `app/core/ai/gemini_client.py` (rule 1)

## Known issues
- The CI workflow (`.github/workflows/ci.yml`) has not run on GitHub yet; its first run is on the Phase 0 PR.
  Every step was verified locally with the same commands.
- Flask-Limiter uses the client IP. Behind nginx (full-Docker/production) every request shows nginx's IP until `ProxyFix` is configured (do this with AUTH-05 / INF-09).
- `RATELIMIT_STORAGE_URI=memory://` counts per gunicorn worker process; fine for dev.

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0 bootstrap: dev environment, app factory, module discovery, error format, OpenAPI docs, health endpoint, worker skeleton, docs and tracker.
