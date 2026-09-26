# marketplace: CA profiles, listings, requests, engagements

## Purpose
CA signup/practice profile, verification (Certificate of Practice), the marketplace listing and matching, requests/quotes/engagements, service catalog with typical prices, pro-bono queue, ratings and objective CA metrics.

## What exists now
Skeleton only; no features yet.
- Backend (`backend/app/modules/marketplace/`): only `__init__.py` and `routes.py`, whose `marketplace` blueprint is registered under `/api/v1` with no routes yet; no models, services or seed data; no tests yet.
- Frontend (`frontend/src/features/marketplace/`): one placeholder page, "Find a CA" at `/business/marketplace` (business nav), built from `ModulePlaceholder`; no API hooks yet.

## Tables
None yet. Planned:
- `ca_profiles`: membership no., CoP, verified flag, city, languages, specializations, capacity, pro-bono pledge
- `service_catalog` (config), `ca_services` (CA price per catalog item)
- `engagements`: business, CA, form/item, status, quote + reason, expiry
- `ratings`, `client_invites`

## Endpoints
None yet. Planned: `/api/v1/marketplace/...`; service catalog admin at `/api/v1/admin/marketplace/...`.

## Service functions other modules call
None yet. Planned: `has_active_engagement(ca_id, business_id)` (used by `ca_has_active_access`), `engagement_status_for(item_id)` (used by compliance).

## Depends on
core-auth (users, roles), compliance (form codes, items), documents (CoP upload), core-infra (worker for 48h expiry).

## Contracts (don't change without telling the team)
- Unverified CAs never appear in listings
- Engagement status codes: `requested → accepted/quoted → active → completed` (plus `declined`/`expired`) (codes and labels: `docs/DATA_MODEL.md`, "Status values")

## Known issues
None yet.
