# Patterns: how to add a feature

> The recipes below follow the conventions already in the code. Building blocks with no working example yet are
> marked "no example yet"; when the first one lands, replace the note with a link to it. Always copy the closest
> existing example instead of inventing a new pattern. **Real, end-to-end examples: see "First feature examples"
> right below Foundations.**

The running example is a made-up `widgets` resource in module `<module>` (e.g. `marketplace`). Read "Foundations"
first: the recipes build on it.

## Where a module's code lives
The code is organised **by layer** (one folder per kind of file), with **one file per module inside each layer**.
A module is therefore a set of files with the same name, not a folder:

| Layer | Backend file | Frontend file |
|---|---|---|
| Model (tables) | `backend/app/models/<module>.py` | |
| Schema (request/response shapes) | `backend/app/schemas/<module>.py` | |
| Service (business logic, DB access) | `backend/app/services/<module>_service.py` | |
| Route (HTTP endpoints) | `backend/app/routes/<module>.py` | |
| Tests | `backend/tests/test_<module>_*.py` | `*.test.jsx` next to the file |
| API hooks | | `frontend/src/api/<module>.js` (camelCase, e.g. `caWorkspace.js`) |
| Pages | | `frontend/src/pages/<role>/<Name>Page.jsx` |
| Seed data | a function in `backend/app/seed.py` | |
| Scheduled job | a line in `backend/worker.py` | |

Shared code, used by every module (call out changes to it in the PR):
`backend/app/{__init__,config,extensions,errors,seed}.py`, `backend/app/models/{base,enums}.py`,
`backend/app/routes/__init__.py`, `backend/app/utils/`; `frontend/src/{routes.jsx,main.jsx}`, `frontend/src/api/client.js`,
`frontend/src/components/`, `frontend/src/context/`, `frontend/src/hooks/`, `frontend/src/lib/`.

Registration is explicit (no auto-discovery): a new blueprint goes into `BLUEPRINTS` in
`backend/app/routes/__init__.py`, a new model into `backend/app/models/__init__.py`, a new page into
`frontend/src/routes.jsx`.

## 0. Foundations
The shared building blocks every feature uses. Each has working code and tests; copy them, don't reinvent them.

### Layering
| Layer | Folder | Does | Never |
|---|---|---|---|
| Route | `routes/` | parse input (`@blp.arguments`), call **one** service function, serialize (`@blp.response`) | query, touch `db.session`, hold business rules |
| Service | `services/` | business logic and all DB access; each public function is one unit of work | query another module's models |
| Model | `models/` | columns, relationships, constraints (data only) | logic, queries, commits |

A module that needs another module's data calls that module's **service functions** (listed in its module doc),
never its models.

### Transactions
- Each public service function is one unit of work: it validates, changes rows, and calls `db.session.commit()`
  **once, at its end**. If something is wrong it raises `ApiError` before committing; Flask-SQLAlchemy rolls the
  session back at the end of the request.
- Helpers that other service functions compose do **not** commit; their docstrings say "Does not commit."
- Worker jobs and `flask seed` follow the same rule (`run_all_seeds()` in `backend/app/seed.py` commits once after
  all seed functions; a seed function does not commit).
- Tests: the `database` fixture (`backend/tests/conftest.py`) wraps each test in one transaction with
  `join_transaction_mode="create_savepoint"`, so a service's `commit()` only releases a savepoint and everything is
  rolled back after the test. Proof: `backend/tests/test_db_foundations.py`.

### Base model
`backend/app/models/base.py`:
- `BaseModel`: every model subclasses it. `id` is a UUID (uuid4, Postgres `uuid`), plus `TimestampMixin`.
- `TimestampMixin`: `created_at`, `updated_at` (timezone-aware UTC; `utcnow()` in Python, `now()` in the DB).
- `SoftDeleteMixin` (opt-in, for user-facing rows): `is_active`, `deleted_at`. Services soft-delete; nothing is
  hard-deleted. Put the mixin first: `class Document(SoftDeleteMixin, BaseModel)`.
- Constraint and index names come from the naming convention in `backend/app/extensions.py`, so Alembic
  migrations are identical on every machine.

### Enums
`backend/app/models/enums.py`:
```python
class WidgetStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"          # values: lowercase snake_case (checked at import)

status: Mapped[WidgetStatus] = mapped_column(str_enum(WidgetStatus))
```
Stored as text (the value, not the member name) with a CHECK constraint `ck_<table>_widget_status`. The API sends
the code; the frontend shows a label from `frontend/src/lib/labels.js`. Status codes and labels are listed in
`docs/DATA_MODEL.md`. Adding a value = hand-written migration replacing the CHECK constraint. An enum used by
several modules goes in `models/enums.py`; one used by a single model can live in that model's file.

### Errors
`backend/app/errors.py`: `raise ApiError(409, "DUPLICATE_WIDGET", "...")` in services (or `abort(404)`).
Every error body is `{"error": {"code", "message", "details?", "request_id"}}`; never build error JSON by hand.

### Logging and request IDs
- `log = logging.getLogger(__name__)` at the top of a file, then `log.info("...")`. No `print`.
- `backend/app/utils/logging_setup.py`:
  - gives every request an ID (incoming `X-Request-ID` or a new one), returns it in the response header and in
    error bodies, and logs one access line per request;
  - adds `request_id` and `job` to every log line, as `LOG_FORMAT=json` (Docker) or `text` (hybrid). The worker
    sets `job` to the job id (`backend/worker.py`). gunicorn uses the same format (`backend/gunicorn.conf.py`).
- Never log PII (PAN, GSTIN, names, emails, phones, document contents); log IDs instead.
- Tests: `backend/tests/test_request_id_and_logging.py`.

### API prefix
Feature blueprints get `/api/v1` from `register_routes()` (`backend/app/routes/__init__.py`); don't set
`url_prefix` on them. `/api/health` and the docs stay unversioned. Tests: `backend/tests/test_api_prefix_and_proxy.py`.

## First feature examples (basic login)
The login feature is the first one built end to end. Copy these files.

**A. Table + migration + seed**
- Model: `backend/app/models/user.py` (`User(SoftDeleteMixin, BaseModel)`, unique email, `str_enum(UserRole)`),
  imported in `backend/app/models/__init__.py`. Shared enum: `UserRole` in `backend/app/models/enums.py`.
- Migration: `backend/migrations/versions/2026_09_25_1912-80850e135434_core_auth_create_users_table.py`
  (autogenerated by `make migration name="core-auth: create users table"`, reviewed, unchanged; the CHECK
  constraint `ck_users_user_role` and `uq_users_email` get their names from the naming convention).
- Seed: `seed_demo_users()` in `backend/app/seed.py` (values from `.env`, idempotent "check before insert", no
  commit), listed in `SEEDS`. Test: `backend/tests/test_seed_command.py` (runs `flask seed` twice,
  `monkeypatch.setenv`).

**B. Service + thin route + schema + role check**
- Service: `authenticate()` in `backend/app/services/auth_service.py`: raises `ApiError` for expected failures,
  commits once at its end. Simpler: `get_dashboard(user)` in `backend/app/services/compliance_service.py`.
- Route: `backend/app/routes/compliance.py`, which is the whole pattern in five lines:
  ```python
  @blp.route("/compliance/dashboard")
  class ComplianceDashboard(MethodView):
      @roles_required(UserRole.BUSINESS)            # 401 without a valid token, 403 for other roles
      @blp.response(200, ComplianceDashboardSchema)
      def get(self):
          return compliance_service.get_dashboard(current_user())
  ```
  Public endpoint + request body + rate limit + documented errors: `Login` in `backend/app/routes/auth.py`.
- Schemas: `backend/app/schemas/compliance.py`; `backend/app/schemas/auth.py` (request vs response).
  Name schemas uniquely across modules (`ComplianceDashboardSchema`, not `DashboardSchema`): the OpenAPI component
  name comes from the class name.
- Role check: `roles_required(*roles)`, `login_required` (any logged-in user) and `current_user()` in
  `backend/app/utils/decorators.py`.
- Tests: `backend/tests/test_compliance_dashboard.py` (allowed role, other roles 403, no token 401) with the
  `make_user` and `auth_headers` fixtures from `backend/tests/conftest.py`; `backend/tests/test_auth_login.py`.

**C. Page + form + API call + guard**
- Page calling the API: `frontend/src/pages/business/BusinessDashboardPage.jsx` with the hook
  `useComplianceDashboard()` in `frontend/src/api/compliance.js`, registered as the business area home
  (`index: true`) in `frontend/src/routes.jsx`.
- Form: `frontend/src/pages/LoginPage.jsx` (React Hook Form + Zod, shadcn `Input`/`Label`/`Button`, one message
  per API error code).
- Guard: `frontend/src/components/RequireRole.jsx`, applied to each role area by `roleArea()` in
  `frontend/src/routes.jsx`; auth state from `useAuth()` (`frontend/src/hooks/useAuth.js`), provided by
  `frontend/src/context/AuthProvider.jsx`.
- Tests: `frontend/src/pages/LoginPage.test.jsx`, `frontend/src/context/AuthProvider.test.jsx`, using
  `fakeApi()`, `loginAs()` and `renderApp()` from `frontend/src/test/utils.jsx`.

## 1. Backend route (flask-smorest)
Existing example: `backend/app/routes/health.py` (schema + route + `alt_response`) and its test
`backend/tests/test_health.py`.

Each module has one Blueprint in `routes/<module>.py` without a `url_prefix` (it is registered under `/api/v1`),
and the module segment is written in every route, so URLs are easy to grep (`/api/v1/<module>/widgets`):

```python
# backend/app/routes/<module>.py
from flask.views import MethodView
from flask_smorest import Blueprint

from app.models.enums import UserRole
from app.schemas.<module> import WidgetCreateSchema, WidgetSchema
from app.services import <module>_service
from app.utils.decorators import current_user, roles_required

blp = Blueprint("<module>", __name__, description="...")

@blp.route("/<module>/widgets")
class Widgets(MethodView):
    @roles_required(UserRole.BUSINESS)          # first: 401/403 before anything else runs
    @blp.response(200, WidgetSchema(many=True))
    def get(self):
        return <module>_service.list_widgets(current_user())

    @roles_required(UserRole.BUSINESS)
    @blp.arguments(WidgetCreateSchema)          # request body validated -> 422 on errors
    @blp.response(201, WidgetSchema)
    def post(self, data):
        return <module>_service.create_widget(current_user(), **data)
```
Then add `<module>.blp` to `BLUEPRINTS` in `backend/app/routes/__init__.py`.

- Routes are thin: validate input (schemas), call one service function, return data. No queries or
  `db.session` in routes (see "Foundations").
- Protect **every** endpoint with `@roles_required(...)` (or `@login_required` for any role) from
  `app/utils/decorators.py` (example: `app/routes/compliance.py`). A public endpoint instead declares
  `@blp.doc(security=[])` (example: `app/routes/auth.py`, login).
- Expected errors: `raise ApiError(409, "DUPLICATE_WIDGET", "A widget with this name exists.")`
  (`app/errors.py`). Never return ad-hoc error JSON.
- Admin endpoints for this module's config: `/api/v1/admin/<module>/...` in the same blueprint.
- After changing routes or schemas: update the frontend calls of those endpoints.

## 2. Schemas (marshmallow)
`schemas/<module>.py` holds request and response shapes. Money: `fields.Decimal(as_string=True, places=2)`.
Timestamps: `fields.DateTime()` (UTC). Dates: `fields.Date()`. See `docs/API_CONVENTIONS.md`.

## 3. Service functions
`services/<module>_service.py` holds business logic and all DB access for the module. Each public function
commits once at its end (see "Foundations", Transactions). Functions listed under "Service functions other
modules call" in the module doc are the module's public interface; other modules call **those functions**,
never this module's models.

## 4. Model + migration
```python
# backend/app/models/<module>.py
from decimal import Decimal
from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel, SoftDeleteMixin
from app.models.enums import str_enum

class Widget(SoftDeleteMixin, BaseModel):     # id (UUID), created_at, updated_at, is_active, deleted_at
    __tablename__ = "widgets"
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # rupees
    status: Mapped[WidgetStatus] = mapped_column(str_enum(WidgetStatus))
```
Working example (test-only): `backend/tests/_models.py`.
- Import the new model in `backend/app/models/__init__.py`, or Alembic will not see its table.
- Soft delete only: add `SoftDeleteMixin` to user-facing entities.
- PAN, GSTIN, TAN, phone use `EncryptedString` + blind index from `app/utils/encryption.py` (no example yet).
- Timestamps are timezone-aware UTC; display in Asia/Kolkata. Financial year = April–March.
- Then: `git pull` on main → `make migration name="<module>: add widgets"` → review the generated file →
  `make migrate`. One migration per PR. Add the table to `docs/DATA_MODEL.md` and your module doc.

## 5. Seed data
Add a `seed_<module>()` function to `backend/app/seed.py` (or, once it grows, a helper it calls) and list it in
`SEEDS`, after anything it depends on (demo users come first). It must be idempotent (check before insert) and
must not commit. Run with `make seed`.

## 6. Scheduled job (worker)
```python
# backend/worker.py, in build_scheduler()
scheduler.add_job(<module>_service.send_widget_digest, "cron", hour=8, id="<module>.widget_digest")
```
Jobs run only in the worker process, inside the Flask app context. Cron times are IST. The job function is a
service function (one unit of work, commits once).

## 7. Tests
- Backend: `backend/tests/test_<module>_*.py`. Fixtures from `backend/tests/conftest.py`: `app`, `client`, and
  `database` (request it in any test that touches the DB; each test runs in one transaction that is rolled back
  afterwards, even when services commit).
- OCR tests: `@pytest.mark.requires_tesseract`.
- Backend auth in tests: `make_user(role=UserRole.CA)` + `client.get(url, headers=auth_headers(user))`.
- Frontend: `*.test.jsx` next to the code, Vitest + React Testing Library (example: `frontend/src/routes.test.jsx`).
  Fake the backend with `fakeApi({"GET /api/v1/...": [200, body]})`, log in with `loginAs(role)` and render with
  `renderApp(path)` (`frontend/src/test/utils.jsx`).

## 8. Frontend page, route and nav link
Example: `frontend/src/pages/business/DocumentsPage.jsx` (a placeholder page) and its entries in
`frontend/src/routes.jsx`.

```tsx
// frontend/src/routes.jsx
export const NAV: Record<Role, NavItem[]> = {
  business: [
    // ...
    { label: "Widgets", path: "/business/widgets" },   // sidebar link, in display order
  ],
  // ...
};

roleArea("business", [
  // ...
  { path: "widgets", element: <WidgetsPage /> },        // -> /business/widgets
]),
```
Areas: public (`/`), business (`/business`), CA (`/ca`), admin (`/admin`); each role's prefix is `ROLE_HOME` in
`frontend/src/lib/session.js`. Each role area is guarded by `RequireRole` inside `roleArea()`, so pages need no
guard of their own. An area's home page is its `{ index: true, element: ... }` route.

## 9. Frontend data fetching
```ts
// frontend/src/api/<module>.js
import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";

export function useWidgets() {
  return useQuery({
    queryKey: ["<module>", "widgets"],
    queryFn: () => unwrap(api.GET("/api/v1/<module>/widgets")),
  });
}
```
`unwrap()` returns the response data or throws `ApiRequestError` (`status`, `code`, `message`, `requestId`). Show
a failure with `errorMessage(query.error)` (adds the request ID as a reference); switch on `error.code` when a
page reacts to a specific error (example: `LOGIN_ERROR_TEXT` in `pages/LoginPage.jsx`). Example hook:
`api/compliance.js`. Field names are the API's snake_case names; look them up in Swagger (`/api/docs`).
Forms: React Hook Form + Zod. A component used by several pages goes in `components/`; one used by a single page
can stay in that page's file.

## 10. Admin screen for a module's config
The module that holds the data also holds its admin endpoints: `/api/v1/admin/<module>/...` in the module's own
blueprint. The page goes in `frontend/src/pages/admin/` and is registered in the `admin` area of
`frontend/src/routes.jsx` (example: `pages/admin/RegulatoryAdminPage.jsx`).

## 11. Calling Gemini or OCR
Only through `app/utils/gemini_client.py` (PII scrubbed) and `app/utils/ocr.py` (local only).
No example yet: neither the Gemini client nor the OCR helpers exist so far.

## Checklist for a new feature
- [ ] route (thin, added to `BLUEPRINTS`) + schema + service (commits once) + tests
- [ ] `@roles_required(...)` on every endpoint (or `@blp.doc(security=[])` if it is public on purpose)
- [ ] model on `BaseModel` (+ `SoftDeleteMixin`, `str_enum()`), imported in `models/__init__.py`, + one migration
      + seed data (if a table was added)
- [ ] frontend page + route + nav link + api hook + test
- [ ] module doc updated (what exists now, tables, endpoints, services, contracts)
