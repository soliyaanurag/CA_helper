# marketplace: CA profiles, listings, requests, engagements

## Purpose
CA signup/practice profile, verification (Certificate of Practice), the marketplace listing and matching, requests/quotes/engagements, service catalog with typical prices, pro-bono queue, ratings and objective CA metrics.

## Owner
Member C (CA side & platform shell)

Folders: `backend/app/modules/marketplace/`, `frontend/src/features/marketplace/`

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [ ] MKT-01 · P1 · C · CA signup profile (membership no., specializations, city, languages) + seeded verified CAs
- [ ] MKT-02 · P1 · C · Marketplace listing with specialization filter, auto-filtered by form code from the item page
- [ ] MKT-03 · P1 · C · Request → accept/decline → engagement + notifications
- [ ] MKT-04 · P2 · C · Standard service catalog + CA service menu with prices + typical price range
- [ ] MKT-05 · P2 · C · Certificate of Practice upload + admin verification flow (unverified hidden)
- [ ] MKT-06 · P2 · C · Engagement lifecycle (Requested → Accepted/Quoted → Active → Completed)
- [ ] MKT-07 · P3 · C · Matching score with reasons
- [ ] MKT-08 · P3 · C · Revised quotes (reason required) + 48h expiry job + re-match
- [ ] MKT-09 · P3 · C · Pro-bono pledge, eligibility, and queue
- [ ] MKT-10 · P3 · C · Ratings and reviews after completion
- [ ] MKT-11 · P3 · C · Certificate of Practice OCR (membership number, name)
- [ ] MKT-12 · P4 · C · Invite existing clients + client approval
- [ ] MKT-13 · P4 · C · Objective CA metrics (on-time rate, verified-filing rate, response time)

## Tables owned
- `ca_profiles` (planned): membership no., CoP, verified flag, city, languages, specializations, capacity, pro-bono pledge
- `service_catalog` (planned config), `ca_services` (planned: CA price per catalog item)
- `engagements` (planned): business, CA, form/item, status, quote + reason, expiry
- `ratings` (planned), `client_invites` (planned, P4)

## Endpoints exposed
Planned: `/api/marketplace/...`; service catalog admin at `/api/admin/marketplace/...` (ADM-03).

## Service functions others may call
- Planned: `has_active_engagement(ca_id, business_id)` (used by `ca_has_active_access`), `engagement_status_for(item_id)` (used by compliance)

## Depends on
core-auth (users, roles), compliance (form codes, items), documents (CoP upload), core-infra (worker for 48h expiry).

## Contracts others rely on
- Unverified CAs never appear in listings
- Engagement statuses: `Requested → Accepted/Quoted → Active → Completed` (plus Declined/Expired)

## Known issues
_None yet._

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0: created this doc and its task list.
