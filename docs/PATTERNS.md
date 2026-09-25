# Patterns: how to add a feature

> **Status: skeleton.** The recipes below follow the conventions already in the code. Several building blocks
> have no working example yet (marked "no example yet"); when the first one lands, replace the note with a link
> to it. Always copy the closest existing example instead of inventing a new pattern.

The running example is a made-up `widgets` resource in module `<module>`.

## 1. Backend route (flask-smorest)
Existing example: `backend/app/core/health.py` (schema + route + `alt_response`) and its test
`backend/tests/test_health.py`.

Each module has one Blueprint in `routes.py` with `url_prefix="/api"`, and the module segment is written in every
route, so URLs are easy to grep:

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

- Routes are thin: validate input (schemas), call `services.py`, return data. No queries in routes.
- Protect **every** endpoint with the shared role decorators from `app/core/permissions.py` (no example yet).
- Expected errors: `raise ApiError(409, "DUPLICATE_WIDGET", "A widget with this name exists.")`
  (`app/core/errors.py`). Never return ad-hoc error JSON.
- Admin endpoints for this module's config: `/api/admin/<module>/...` in the same blueprint.
- After adding/changing routes or schemas: `make gen-api`.

## 2. Schemas (marshmallow)
`schemas.py` holds request and response shapes. Money: `fields.Decimal(as_string=True, places=2)`.
Timestamps: `fields.DateTime()` (UTC). Dates: `fields.Date()`. See `docs/API_CONVENTIONS.md`.

## 3. Service functions
`services.py` holds business logic and all DB access for the module. Functions listed under
"Service functions other modules call" in the module doc are the module's public interface; other modules import
**those functions**, never this module's models.

## 4. Model + migration
```python
# app/modules/<module>/models.py
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from app.extensions import db

class Widget(db.Model):
    __tablename__ = "widgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(200))
    price: Mapped[Decimal] = mapped_column(db.Numeric(12, 2))  # rupees
```
- Soft delete only (`is_active` / `deleted_at`); shared mixins are planned in core/db (not built yet).
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
  `database` (request it in any test that touches the DB; rows are deleted after each test).
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
      const { data, error } = await api.GET("/api/<module>/widgets");
      if (error) throw new Error(error.error.message);
      return data;
    },
  });
}
```
Types come from the generated OpenAPI types. Never hand-write API types. Forms: React Hook Form + Zod.

## 10. Admin screen for a module's config
The module that holds the data also holds its admin screen. Backend under `/api/admin/<module>/...`; frontend
page in `features/<module>/admin/`, registered under the `admin` key of the module's `routes.tsx` (example:
`features/regulatory/routes.tsx`).

## 11. Calling Gemini or OCR
Only through `app/core/ai/gemini_client.py` (PII scrubbed) and `app/core/ocr/` (local only).
No example yet: neither the Gemini client nor the OCR helpers exist so far.

## Checklist for a new feature
- [ ] route + schema + service + tests
- [ ] access control decorator on every endpoint
- [ ] model + one migration + seed data (if a table was added)
- [ ] `make gen-api`, frontend page + route + api hook + test
- [ ] module doc updated (what exists now, tables, endpoints, services, contracts)
