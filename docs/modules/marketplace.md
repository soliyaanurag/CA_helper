# marketplace: CA profiles, listings, requests, engagements

## Purpose
CA signup/practice profile, verification (Certificate of Practice), the marketplace listing and matching, requests/quotes/engagements, service catalog with typical prices, pro-bono queue, ratings and objective CA metrics.

## What exists now
CA practice profiles (MA1), verification by numbers (MA2, the certificate upload comes later) and the list of
verified CAs businesses browse.
- **Backend:** model `CaProfile` + `CaVerificationStatus`, `CA_SPECIALIZATIONS`, `CA_LANGUAGES` in
  `app/models/marketplace.py`; schemas in `app/schemas/marketplace.py` (the list uses the shared
  `app/schemas/pagination.py`); logic in `app/services/marketplace_service.py`; routes in
  `app/routes/marketplace.py` (in `BLUEPRINTS`). Migration `…_marketplace_add_ca_profiles.py`.
- **Seed:** `seed_ca_profiles()` in `app/seed.py`: the demo CA gets a verified profile; four sample verified CAs
  (`sample-ca-1..4@demo.local`, cannot log in) fill the list.
- **Frontend:** `pages/ca/CaProfilePage.jsx` at `/ca/profile` (CA nav "My profile"): the form, the verification
  status and what it means. `pages/ca/CaDashboardPage.jsx` shows a reminder card until the profile is verified.
  `pages/business/MarketplacePage.jsx` at `/business/marketplace` ("Find a CA"): verified CAs as cards, filters
  for specialization, language and city kept in the URL (`?specialization=itr`), Previous/Next pages. Hooks in
  `api/marketplace.js` (`useCaProfile` → `null` before the first save, `saveCaProfile`, `useVerifiedCas`); labels
  in `lib/labels.js`.
- **Tests:** `tests/test_marketplace_ca_profile.py`, `tests/test_marketplace_ca_list.py`,
  `tests/test_seed_command.py`; `CaProfilePage.test.jsx`, `MarketplacePage.test.jsx`.
- **Not yet:** Certificate of Practice upload + OCR, the admin verify/reject screen, service catalog and prices,
  requests/engagements, pro-bono, ratings.

## Tables
- `ca_profiles`: one CA's practice profile and verification status (details in `docs/DATA_MODEL.md`)

Planned:
- `service_catalog` (config), `ca_services` (CA price per catalog item)
- `engagements`: business, CA, form/item, status, quote + reason, expiry
- `ratings`, `client_invites`

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/v1/marketplace/ca-profile` | ca | the CA's own profile; 404 `CA_PROFILE_NOT_FOUND` before the first save |
| PUT | `/api/v1/marketplace/ca-profile` | ca | create or update `{membership_no, cop_number, city, languages[], specializations[], capacity, years_experience, about}` → the profile; 409 `DUPLICATE_MEMBERSHIP_NO` |
| GET | `/api/v1/marketplace/cas?specialization=&language=&city=&page=&page_size=` | business | `{items, page, page_size, total}`: verified CAs with live accounts, most experienced first; each item `{id, full_name, membership_no, city, languages, specializations, years_experience, about}` (no CoP number, no capacity) |

`city` matches any part of the city name, any case. Planned: requests/engagements under
`/api/v1/marketplace/...`; admin verification and the service catalog under `/api/v1/admin/...`.

## Service functions other modules call
None yet. Planned: `has_active_engagement(ca_id, business_id)` (used by `ca_has_active_access`), `engagement_status_for(item_id)` (used by compliance).

## Depends on
core-auth (users, roles), compliance (form codes, items), documents (CoP upload), core-infra (worker for 48h expiry).

## Contracts (don't change without telling the team)
- Unverified CAs never appear in listings (`list_verified_cas()` filters on `verified` and a live account)
- `verification_status` codes `pending` / `verified` / `rejected`, and the specialization and language codes
  (codes and labels: `docs/DATA_MODEL.md`, "Status values"); the first seven specializations are the form codes
  compliance will filter on (`/business/marketplace?specialization=gstr_3b`)
- Engagement status codes: `requested → accepted/quoted → active → completed` (plus `declined`/`expired`)

## Known issues
- No admin screen yet: a newly signed-up CA stays `pending` and is not listed. For local testing, verify by hand:
  `docker compose exec db psql -U ca_helper -d ca_helper -c "UPDATE ca_profiles SET verification_status = 'verified'"`
