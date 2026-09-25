# Patterns: how to add a feature

> **Status: skeleton.** The recipes below follow the conventions already in the code. Several building blocks
> have no working example yet (marked "no example yet"); when the first one lands, replace the note with a link
> to it. Always copy the closest existing example instead of inventing a new pattern.

The running example is a made-up `widgets` resource in module `<module>`. Read "Foundations" first: the recipes
build on it.

## 0. Foundations
The shared building blocks every feature uses. Each has working code and tests; copy them, don't reinvent them.

### Layering
| Layer | File | Does | Never |
|---|---|---|---|
| Route | `routes.py` | parse input (`@blp.arguments`), call **one** service function, serialize (`@blp.response`) | query, touch `db.session`, hold business rules |
| Service | `services.py` | business logic and all DB access; each public function is one unit of work | import another module's models |
| Model | `models.py` | columns, relationships, constraints (data only) | logic, queries, commits |

Other modules call a module's **service functions** (listed in its module doc), never its models.

### Transactions
- Each public service function is one unit of work: it validates, changes rows, and calls `db.session.commit()`
  **once, at its end**. If something is wrong it raises `ApiError` before committing; Flask-SQLAlchemy rolls the
  session back at the end of the request.
- Helpers that other service functions compose do **not** commit; their docstrings say "Does not commit."
- Worker jobs and `flask seed` follow the same rule (`run_all_seeds()` in `backend/app/modules/__init__.py` commits
  once after all seeds; a `seed()` does not commit).
- Tests: the `database` fixture (`backend/conftest.py`) wraps each test in one transaction with
  `join_transaction_mode="create_savepoint"`, so a service's `commit()` only releases a savepoint and everything is
  rolled back after the test. Proof: `backend/tests/test_db_foundations.py`.

### Base model
`backend/app/core/db/models.py`:
- `BaseModel`: every model subclasses it. `id` is a UUID (uuid4, Postgres `uuid`), plus `TimestampMixin`.
- `TimestampMixin`: `created_at`, `updated_at` (timezone-aware UTC; `utcnow()` in Python, `now()` in the DB).
- `SoftDeleteMixin` (opt-in, for user-facing rows): `is_active`, `deleted_at`. Services soft-delete; nothing is
  hard-deleted. Put the mixin first: `class Document(SoftDeleteMixin, BaseModel)`.
- Constraint and index names come from the naming convention in `backend/app/core/db/base.py`, so Alembic
  migrations are identical on every machine.

### Enums
`backend/app/core/db/enums.py`:
```python
class WidgetStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"          # values: lowercase snake_case (checked at import)

status: Mapped[WidgetStatus] = mapped_column(str_enum(WidgetStatus))
```
Stored as text (the value, not the member name) with a CHECK constraint `ck_<table>_widget_status`. The API sends
the code; the frontend shows a label from `frontend/src/core/labels.ts`. Status codes and labels are listed in
`docs/DATA_MODEL.md`. Adding a value = hand-written migration replacing the CHECK constraint.

### Errors
`backend/app/core/errors.py`: `raise ApiError(409, "DUPLICATE_WIDGET", "...")` in services (or `abort(404)`).
Every error body is `{"error": {"code", "message", "details?", "request_id"}}`; never build error JSON by hand.

### Logging and request IDs
- `log = logging.getLogger(__name__)` at the top of a file, then `log.info("...")`. No `print`.
- `backend/app/core/request_id.py` gives every request an ID (incoming `X-Request-ID` or a new one), returns it in
  the response header and in error bodies, and logs one access line per request.
- `backend/app/core/logging_config.py` adds `request_id` and `job` to every line; `LOG_FORMAT=json` (Docker) or
  `text` (hybrid). The worker sets `job` to the job id (`backend/worker.py`). gunicorn uses the same format
  (`backend/gunicorn.conf.py`).
- Never log PII (PAN, GSTIN, names, emails, phones, document contents); log IDs instead.
- Tests: `backend/tests/test_request_id_and_logging.py`.

### API prefix
Module blueprints get `/api/v1` from `register_blueprints()`; don't set `url_prefix` in a module. `/api/health`
and the docs stay unversioned. Tests: `backend/tests/test_api_prefix_and_proxy.py`.

## 1. Backend route (flask-smorest)
Existing example: `backend/app/core/health.py` (schema + route + `alt_response`) and its test
`backend/tests/test_health.py`.

Each module has one Blueprint in `routes.py` without a `url_prefix` (it is registered under `/api/v1`), and the
module segment is written in every route, so URLs are easy to grep (`/api/v1/<module>/widgets`):

```python
# app/modules/<module>/routes.py
from flask.views import MethodView

from app.modules.<module> import services
from app.modules.<module>.schemas import WidgetCreateSchema, WidgetSchema

@blp.route("/<module>/widgets")
class Widgets(MethodView):
    @blp.response(200, WidgetSchema(many=True))
    def get(self):
        return services.list_widgets(...)

    @blp.arguments(WidgetCreateSchema)          # request body validated -> 422 on errors
    @blp.response(201, WidgetSchema)
    def post(self, data):
        return services.create_widget(**data)
```

- Routes are thin: validate input (schemas), call one service function, return data. No queries or
  `db.session` in routes (see "Foundations").
- Protect **every** endpoint with the shared role decorators from `app/core/permissions.py` (no example yet).
- Expected errors: `raise ApiError(409, "DUPLICATE_WIDGET", "A widget with this name exists.")`
  (`app/core/errors.py`). Never return ad-hoc error JSON.
- Admin endpoints for this module's config: `/api/v1/admin/<module>/...` in the same blueprint.
- After adding/changing routes or schemas: `make gen-api`.

## 2. Schemas (marshmallow)
`schemas.py` holds request and response shapes. Money: `fields.Decimal(as_string=True, places=2)`.
Timestamps: `fields.DateTime()` (UTC). Dates: `fields.Date()`. See `docs/API_CONVENTIONS.md`.

## 3. Service functions
`services.py` holds business logic and all DB access for the module. Each public function commits once at its
end (see "Foundations", Transactions). Functions listed under
"Service functions other modules call" in the module doc are the module's public interface; other modules import
**those functions**, never this module's models.

## 4. Model + migration
```python
# app/modules/<module>/models.py
from decimal import Decimal
from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.enums import str_enum
from app.core.db.models import BaseModel, SoftDeleteMixin

class Widget(SoftDeleteMixin, BaseModel):     # id (UUID), created_at, updated_at, is_active, deleted_at
    __tablename__ = "widgets"
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # rupees
    status: Mapped[WidgetStatus] = mapped_column(str_enum(WidgetStatus))
```
Working example (test-only): `backend/tests/_models.py`.
- Soft delete only: add `SoftDeleteMixin` to user-facing entities.
- PAN, GSTIN, TAN, phone use `EncryptedString` + blind index from core/security (no example yet).
- Timestamps are timezone-aware UTC; display in Asia/Kolkata. Financial year = April–March.
- Then: `git pull` on main → `make migration name="<module>: add widgets"` → review the generated file →
  `make migrate`. One migration per PR. Add the table to `docs/DATA_MODEL.md` and your module doc.

## 5. Seed data
`seed.py` → `seed()` must be idempotent (check before insert). Set `SEED_ORDER` in the module `__init__.py` if it
depends on another module's seed (lower runs first; default 100). Run with `make seed`.

## 6. Scheduled job (worker)
```python
# app/modules/<module>/__init__.py
def register_jobs(scheduler):
    scheduler.add_job(services.send_widget_digest, "cron", hour=8, id="<module>.widget_digest")
```
Jobs run only in the worker process, inside the Flask app context. Cron times are IST. See `backend/worker.py`.

## 7. Tests
- Backend: `app/modules/<module>/tests/test_*.py`. Fixtures from `backend/conftest.py`: `app`, `client`, and
  `database` (request it in any test that touches the DB; each test runs in one transaction that is rolled back
  afterwards, even when services commit).
- OCR tests: `@pytest.mark.requires_tesseract`.
- Frontend: `*.test.tsx` next to the code, Vitest + React Testing Library (example: `frontend/src/core/routes.test.tsx`).

## 8. Frontend page, route and nav link
Existing example: any `frontend/src/features/<module>/routes.tsx` and its placeholder page.

```tsx
// features/<module>/routes.tsx: picked up automatically by core/routes.tsx
export const routes: FeatureRoutes = {
  business: {
    routes: [{ path: "widgets", element: <WidgetsPage /> }],           // -> /app/widgets
    nav: [{ label: "Widgets", path: "widgets", order: 70 }],
  },
};
```
Areas: `public` (/), `business` (/app), `ca` (/ca), `admin` (/admin). No central route list to edit.

## 9. Frontend data fetching
```ts
// features/<module>/api.ts
export function useWidgets() {
  return useQuery({
    queryKey: ["<module>", "widgets"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/<module>/widgets");
      if (error) throw new Error(error.error.message);
      return data;
    },
  });
}
```
Types come from the generated OpenAPI types. Never hand-write API types. Forms: React Hook Form + Zod.

## 10. Admin screen for a module's config
The module that holds the data also holds its admin screen. Backend under `/api/v1/admin/<module>/...`; frontend
page in `features/<module>/admin/`, registered under the `admin` key of the module's `routes.tsx` (example:
`features/regulatory/routes.tsx`).

## 11. Calling Gemini or OCR
Only through `app/core/ai/gemini_client.py` (PII scrubbed) and `app/core/ocr/` (local only).
No example yet: neither the Gemini client nor the OCR helpers exist so far.

## Checklist for a new feature
- [ ] route (thin) + schema + service (commits once) + tests
- [ ] access control decorator on every endpoint
- [ ] model on `BaseModel` (+ `SoftDeleteMixin`, `str_enum()`) + one migration + seed data (if a table was added)
- [ ] `make gen-api`, frontend page + route + api hook + test
- [ ] module doc updated (what exists now, tables, endpoints, services, contracts)
