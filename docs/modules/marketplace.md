# marketplace: CA profiles, listings, requests, engagements

## Purpose
CA signup/practice profile, verification (Certificate of Practice), the marketplace listing and matching, requests/quotes/engagements, service catalog with typical prices, pro-bono queue, ratings and objective CA metrics.

## What exists now
Skeleton only; no features yet.
- Backend (`backend/app/modules/marketplace/`): the `marketplace` blueprint is registered under `/api` with no routes; `models.py`, `schemas.py` and `services.py` are empty; `seed()` does nothing; `tests/` is empty.
- Frontend (`frontend/src/features/marketplace/`): one placeholder page, "Find a CA" at `/app/marketplace` (business nav), built from `ModulePlaceholder`; `api.ts` is empty.

## Tables
None yet. Planned:
- `ca_profiles`: membership no., CoP, verified flag, city, languages, specializations, capacity, pro-bono pledge
- `service_catalog` (config), `ca_services` (CA price per catalog item)
- `engagements`: business, CA, form/item, status, quote + reason, expiry
- `ratings`, `client_invites`

## Endpoints
None yet. Planned: `/api/marketplace/...`; service catalog admin at `/api/admin/marketplace/...`.

## Service functions other modules call
None yet. Planned: `has_active_engagement(ca_id, business_id)` (used by `ca_has_active_access`), `engagement_status_for(item_id)` (used by compliance).

## Depends on
core-auth (users, roles), compliance (form codes, items), documents (CoP upload), core-infra (worker for 48h expiry).

## Contracts (don't change without telling the team)
- Unverified CAs never appear in listings
- Engagement statuses: `Requested → Accepted/Quoted → Active → Completed` (plus Declined/Expired) (authoritative list: `docs/DATA_MODEL.md`, "Status values")

## Known issues
None yet.
