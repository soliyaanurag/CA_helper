# marketplace: CA profiles, listings, requests, engagements

## Purpose
CA signup/practice profile, verification (Certificate of Practice), the marketplace listing and matching, requests/quotes/engagements, service catalog with typical prices, pro-bono queue, ratings and objective CA metrics.

## What exists now
CA practice profiles (MA1), verification by numbers (MA2, the certificate upload comes later), the list of
verified CAs businesses browse, the CA price menu (MA5) and the typical price range per service (MA6).
- **Backend:** models `CaProfile` + `CaVerificationStatus`, `CA_SPECIALIZATIONS`, `CA_LANGUAGES`,
  `CatalogService` + `ServiceUnit`, `CaService` in `app/models/marketplace.py`; schemas in `app/schemas/marketplace.py` (the list uses the shared
  `app/schemas/pagination.py`); logic in `app/services/marketplace_service.py`; routes in
  `app/routes/marketplace.py` (in `BLUEPRINTS`). Migrations
  `…_marketplace_add_ca_profiles.py`, `…_marketplace_add_service_catalog_and_ca_.py`.
- **Seed:** `seed_ca_profiles()` in `app/seed.py`: the demo CA gets a verified profile; four sample verified CAs
  (`sample-ca-1..4@demo.local`, cannot log in) fill the list. `seed_service_catalog()` adds the 13 catalog
  services (`SERVICE_CATALOG`); `seed_ca_prices()` gives the four sample CAs made-up prices (`SAMPLE_PRICES`), so
  ITR-3, ITR-4 and GSTR-3B reach three CAs and show a range. The demo CA gets no prices (set them on `/ca/services`).
- **Frontend:** `pages/ca/CaProfilePage.jsx` at `/ca/profile` (CA nav "My profile"): the form, the verification
  status and what it means. `pages/ca/CaDashboardPage.jsx` shows a reminder card until the profile is verified.
  `pages/ca/CaServicesPage.jsx` at `/ca/services` (CA nav "Services & prices"): tick a service, enter the fee,
  see the typical range and "Below / At / Above the median"; needs a saved profile.
  `pages/business/MarketplacePage.jsx` at `/business/marketplace` ("Find a CA"): verified CAs as cards, filters
  for service, specialization, language and city kept in the URL (`?service=gstr_3b`), Previous/Next pages; with
  a service chosen, the typical fee and each CA's price; clicking anywhere on a card opens
  `pages/business/CaDetailPage.jsx` at `/business/marketplace/:caId` (no nav link): profile, specializations,
  languages and a "Services & fees" table (the CA's fee, below/at/above the median, the typical range); "Back to
  results" keeps the filters. `pages/business/TypicalFeesPage.jsx` at `/business/fees`
  (business nav "Typical fees"): every service's lowest / median / highest fee, linking to "Find a CA". Hooks in
  `api/marketplace.js` (`useCaProfile` → `null` before the first save, `saveCaProfile`, `useVerifiedCas`,
  `useVerifiedCa`, `useServices`, `useCaServices`, `saveCaServices`); labels in `lib/labels.js`; `formatRupees`,
  `typicalRangeText`, `comparedToMedian` in `lib/money.js`.
- **Tests:** `tests/test_marketplace_ca_profile.py`, `tests/test_marketplace_ca_list.py`,
  `tests/test_marketplace_services.py`, `tests/test_marketplace_ca_detail.py`, `tests/test_seed_command.py`;
  `CaProfilePage.test.jsx`, `CaServicesPage.test.jsx`, `MarketplacePage.test.jsx`, `CaDetailPage.test.jsx`, `TypicalFeesPage.test.jsx`, `lib/money.test.js`.
- **Not yet:** Certificate of Practice upload + OCR, the admin verify/reject screen, the admin catalog editor,
  requests/engagements (a "Request this CA" button on the CA page), pro-bono, ratings (a section on the CA page).

## Tables
- `ca_profiles`: one CA's practice profile and verification status (details in `docs/DATA_MODEL.md`). The
  `schema: complete data model` migration added `pro_bono_slots_per_month` (≥ 0), `rejection_reason`,
  `verified_at`, `verified_by_id` (the admin) and `cop_document_id` (the Certificate of Practice document); no
  code uses them yet. The existing names stay: `about` is the bio, `capacity` the max active clients.
  `CaProfile.user` names its foreign key (`foreign_keys=[user_id]`) because the table now has two links to `users`.
- `service_catalog` (`CatalogService`): the standard services every CA prices against (seeded; config data). New
  `form_code` (null for services that are not one filing), not seeded yet.
- `ca_services`: one CA's price for one catalog service (soft-deleted when the CA stops offering it)

Created by `schema: complete data model`, not used by any service yet (model file `app/models/marketplace.py`):
- `engagements`: business + CA, status (`requested`, `quoted`, `active`, `completed`, `declined`, `expired`,
  `cancelled`; no `accepted`), pro bono, quote reason, requested/responded/expires/activated/completed times
- `engagement_items`: the filings of an engagement, with service, listed and agreed price; unique per engagement
- `ratings` (1–5 stars, one per engagement), `client_invites` (token hash only), `pro_bono_requests`
- **Invariant for the engagement service (not enforceable in the database):** a compliance item is in at most one
  open engagement (`requested`, `quoted`, `active`).

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/v1/marketplace/ca-profile` | ca | the CA's own profile; 404 `CA_PROFILE_NOT_FOUND` before the first save |
| PUT | `/api/v1/marketplace/ca-profile` | ca | create or update `{membership_no, cop_number, city, languages[], specializations[], capacity, years_experience, about}` → the profile; 409 `DUPLICATE_MEMBERSHIP_NO` |
| GET | `/api/v1/marketplace/cas?service=&specialization=&language=&city=&page=&page_size=` | business | `{items, page, page_size, total}`: verified CAs with live accounts, most experienced first; each item `{id, full_name, membership_no, city, languages, specializations, years_experience, about, price}` (no CoP number, no capacity). `service` (a catalog code) keeps CAs who offer it and fills `price`; otherwise `price` is null |
| GET | `/api/v1/marketplace/cas/<id>` | business | one listed CA: `{id, full_name, membership_no, city, languages, specializations, years_experience, about, services}`; `services` are the catalog services they offer, in catalog order, each a catalog row (with the typical range) plus the CA's `price`. 404 `CA_NOT_FOUND` for a CA who is not verified or whose account is not live (same rule as the list) |
| GET | `/api/v1/marketplace/services` | any logged-in | active catalog services in order: `{id, code, name, description, unit, ca_count, min_price, median_price, max_price}`; the three prices are null until `MIN_CAS_FOR_RANGE` (3) listed CAs offer the service |
| GET | `/api/v1/marketplace/ca-services` | ca | `{items: [{service_id, price}]}`: the CA's current menu (empty without a profile) |
| PUT | `/api/v1/marketplace/ca-services` | ca | body `{items: [{service_id, price}]}` replaces the menu → the saved menu; price 1 to 10,00,000; 404 `CA_PROFILE_NOT_FOUND`, 400 `UNKNOWN_SERVICE` (not in the active catalog) |

`city` matches any part of the city name, any case. Money is sent as a string with two decimals (`"750.00"`). Planned: requests/engagements under
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
- Typical price range: only verified CAs with live accounts and current (active) prices count; shown only from
  3 CAs; median, not average; computed on every request, never stored or typed in
- Service codes (`service_catalog.code`) are what `?service=` and future links use (e.g. from a compliance item);
  unit codes: `docs/DATA_MODEL.md`
- Engagement status codes: `requested → active` (CA accepts the listed prices) or `requested → quoted → active`
  (business accepts the quote), then `completed`; plus `declined`, `expired` (48 hours), `cancelled` (by the
  business). No `accepted`. Open = `requested`, `quoted`, `active`; at most one open engagement per filing
- `ca_profiles` and `service_catalog` are never re-inserted after soft delete. Removing then re-adding
  reactivates the existing row (keeps `user_id`/`membership_no`/`code` unique). Same as `ca_services`, whose
  rows `save_own_menu()` already reactivates.

## Known issues
- Nothing soft-deletes a CA profile or a catalog service yet. The planned admin "remove" and the admin catalog
  editor must follow the rule above: inserting a new row for the same user, membership number or code fails on
  the plain UNIQUE constraint.
- No admin screen yet: a newly signed-up CA stays `pending` and is not listed. For local testing, verify by hand:
  `docker compose exec db psql -U ca_helper -d ca_helper -c "UPDATE ca_profiles SET verification_status = 'verified'"`
