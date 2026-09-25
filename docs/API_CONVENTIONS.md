# API conventions

Applies to every endpoint. The live spec is at `/api/docs` (Swagger UI) and `/api/openapi.json`;
`make gen-api` turns it into TypeScript types for the frontend.

## URLs
- Everything is under `/api`.
- Module resources: `/api/<module>/<resource>`, with kebab-case segments and plural nouns:
  `/api/compliance/items`, `/api/compliance/items/{item_id}`, `/api/ca-workspace/clients`.
- Actions that are not plain CRUD use a verb sub-path: `POST /api/compliance/items/{item_id}/mark-filed`.
- Admin endpoints for a module's configuration: `/api/admin/<module>/...`, in that module's blueprint.
- Core endpoints: `/api/health` (exists), `/api/auth/...` and `/api/notifications/...` (planned).
- No `/v1` in URLs. There is one version, and the spec plus generated types keep both sides in sync.

## JSON
- Keys are `snake_case` (the same names as in Python and in the generated TypeScript types).
- **Timestamps:** ISO 8601 in UTC, e.g. `"2026-09-25T08:30:00Z"`. The frontend displays them in Asia/Kolkata.
- **Dates** (due dates, periods): `"YYYY-MM-DD"`, no time zone.
- **Money:** rupees as a decimal **string** with 2 places, e.g. `"1250.00"`
  (`fields.Decimal(as_string=True, places=2)`), never a float.
- **Financial year:** a string like `"2026-27"` (April–March).
- Enums are lowercase strings (`"business"`, `"ca"`, `"admin"`). Compliance and engagement statuses use the exact values in `docs/DATA_MODEL.md` ("Status values").

## Authentication
- `Authorization: Bearer <access_token>` (JWT). The token carries a `role` claim: `business` | `ca` | `admin`.
- Refresh tokens get new access tokens via the refresh endpoint (details fixed when auth is built).
- Every endpoint except health, docs, signup/login/OTP is protected by a role decorator from `core/permissions.py`.
- A CA reads business data only via `ca_has_active_access(ca_id, business_id)`.

## Errors
Every error response has the same body (built in `backend/app/core/errors.py`):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Some fields are invalid.",
    "details": {"json": {"pan": ["Invalid PAN format."]}}
  }
}
```

- `code`: stable UPPER_SNAKE_CASE; defaults to the HTTP status name (`NOT_FOUND`, `FORBIDDEN`, ...), and 422 is
  `VALIDATION_ERROR`. Domain errors use specific codes: `raise ApiError(409, "DUPLICATE_PAN", "...")`.
- `message`: human-readable, safe to show.
- `details`: optional; for 422 it maps location (`json`, `query`, ...) → field → messages.
- Never put PII or stack traces in error messages.

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
