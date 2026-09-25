# API conventions

Applies to every endpoint. The live spec is at `/api/docs` (Swagger UI) and `/api/openapi.json`;
`make gen-api` turns it into TypeScript types for the frontend.

## URLs
- **Every API route is under `/api/v1`.** `register_blueprints()` (`backend/app/modules/__init__.py`) adds the
  prefix to every module blueprint, so blueprints set no `url_prefix` of their own.
- **Unversioned (infrastructure only):** `/api/health` (Docker/CI healthchecks, the frontend status badge),
  `/api/docs` (Swagger UI) and `/api/openapi.json`.
- The API's bare root `/` redirects to `/api/docs` (the API serves no pages; the app is the frontend).
- Module resources: `/api/v1/<module>/<resource>`, with kebab-case segments and plural nouns:
  `/api/v1/compliance/items`, `/api/v1/compliance/items/{item_id}`, `/api/v1/ca-workspace/clients`.
- Actions that are not plain CRUD use a verb sub-path: `POST /api/v1/compliance/items/{item_id}/mark-filed`.
- Admin endpoints for a module's configuration: `/api/v1/admin/<module>/...`, in that module's blueprint.
- Core endpoints: `/api/health`, `/api/v1/auth/login`, `/api/v1/auth/me` (exist); more of `/api/v1/auth/...` and
  `/api/v1/notifications/...` (planned).
- An area's home-page data is served by the module that owns that page, under its own segment:
  `/api/v1/compliance/dashboard` (business), `/api/v1/ca-workspace/dashboard` (CA), `/api/v1/admin/dashboard`.
- A breaking change would get a new prefix (`/api/v2`) next to the old one; nothing needs that yet.
- The Vite proxy (hybrid) and nginx (Docker) forward all of `/api/`, which covers both. The frontend client uses
  `baseUrl: ""` because the generated paths already contain `/api/v1` (`frontend/src/core/api/client.ts`).

## JSON
- Keys are `snake_case` (the same names as in Python and in the generated TypeScript types).
- **IDs** are UUID strings, e.g. `"8c9e6679-7425-40de-944b-e07fc1f90ae7"` (`fields.UUID()`); path parameters
  like `{item_id}` too.
- **Timestamps:** ISO 8601 in UTC, e.g. `"2026-09-25T08:30:00Z"`. The frontend displays them in Asia/Kolkata.
- **Dates** (due dates, periods): `"YYYY-MM-DD"`, no time zone.
- **Money:** rupees as a decimal **string** with 2 places, e.g. `"1250.00"`
  (`fields.Decimal(as_string=True, places=2)`), never a float.
- **Financial year:** a string like `"2026-27"` (April–March).
- **Enums** are lowercase snake_case codes (`"business"`, `"docs_pending"`), the same values the database
  stores. The codes and their display labels are listed in `docs/DATA_MODEL.md` ("Status values"). The API never
  sends display text for an enum; the frontend maps codes to labels in `frontend/src/core/labels.ts`.

## Authentication
- `POST /api/v1/auth/login` `{email, password}` → `{access_token, user}`; rate limited to 10 per minute per IP.
- `Authorization: Bearer <access_token>` (JWT). `sub` is the user id; a `role` claim is `business` | `ca` |
  `admin`; the lifetime is `JWT_ACCESS_TOKEN_MINUTES` (default 60). No refresh token yet (planned).
- Every endpoint except health, docs, signup/login/OTP is protected by `@roles_required(...)` from
  `app/core/permissions.py`, which checks the role stored in the database. In the OpenAPI spec bearer auth is the
  global default; public endpoints declare `@blp.doc(security=[])`.
- Auth error codes: 401 `AUTH_REQUIRED` (no token), `TOKEN_INVALID`, `TOKEN_EXPIRED`, `ACCOUNT_INACTIVE` (user
  deactivated), `INVALID_CREDENTIALS` (login); 403 `FORBIDDEN` (wrong role), `ACCOUNT_INACTIVE` (login);
  429 `TOO_MANY_REQUESTS`. The frontend logs out on any 401 to a request that carried a token.
- A CA reads business data only via `ca_has_active_access(ca_id, business_id)`.

## Errors
Every error response has the same body (built in `backend/app/core/errors.py`):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Some fields are invalid.",
    "details": {"json": {"pan": ["Invalid PAN format."]}},
    "request_id": "3f2a9c1e0b7d4e5f8a6b2c1d0e9f8a7b"
  }
}
```

- `code`: stable UPPER_SNAKE_CASE; defaults to the HTTP status name (`NOT_FOUND`, `FORBIDDEN`, ...), and 422 is
  `VALIDATION_ERROR`. Domain errors use specific codes: `raise ApiError(409, "DUPLICATE_PAN", "...")`.
- `message`: human-readable, safe to show.
- `details`: optional; for 422 it maps location (`json`, `query`, ...) → field → messages.
- `request_id`: the request's ID (see "Request IDs" below). Show it to users with unexpected errors ("quote this
  ID") so the matching log lines can be found.
- Never put PII or stack traces in error messages.
- Frontend: every call goes through `unwrap()` (`frontend/src/core/api/errors.ts`), which turns this body into an
  `ApiRequestError` with `status`, `code`, `message` and `requestId`.

## Request IDs
- Every response has an `X-Request-ID` header. If the request carried a valid `X-Request-ID` (1–128 characters of
  `A-Z a-z 0-9 . _ -`), the same value is returned; otherwise the API generates one (32 hex characters).
- The same ID is in every log line written while handling the request and in every error body
  (`backend/app/core/request_id.py`, `backend/app/core/logging_config.py`).

## Status codes
| Code | When |
|---|---|
| 200 | Successful GET, PUT, PATCH, or an action that returns data |
| 201 | Resource created (POST) |
| 204 | Success with no body (e.g. soft DELETE) |
| 400 | Malformed request |
| 401 | Not logged in / token invalid or expired |
| 403 | Logged in but not allowed (wrong role, no active CA access) |
| 404 | Not found, **or** exists but the caller may not know it exists |
| 409 | Conflict (duplicate, invalid state transition) |
| 422 | Validation error (automatic from `@blp.arguments`) |
| 429 | Rate limited (login, OTP) |
| 500 | Unexpected server error |

## Pagination
List endpoints that can grow take `?page=1&page_size=20` (`page` starts at 1; `page_size` default 20, max 100) and return:

```json
{"items": [...], "page": 1, "page_size": 20, "total": 57}
```
A shared schema/helper for this is added with the first paginated endpoint.

## Filtering and sorting
Plain query parameters named after fields: `?status=overdue&form_code=GSTR-3B&sort=due_date` (`-due_date` for descending).

## Deletion
`DELETE` performs a **soft delete** (`is_active=false`, `deleted_at=now`) and returns 204. Nothing is hard-deleted.
