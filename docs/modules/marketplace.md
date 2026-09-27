# marketplace: CA profiles, listings, requests, engagements

## Purpose
CA signup/practice profile, verification (Certificate of Practice), the marketplace listing and matching, requests/quotes/engagements, service catalog with typical prices, pro-bono queue, ratings and objective CA metrics.

## What exists now
CA practice profiles (MA1), verification by numbers (MA2, the certificate upload comes later), the list of
verified CAs businesses browse, the CA price menu (MA5), the typical price range per service (MA6), and
engagements: sending a request (MA9), the CA's answer and the business's decision on a quote (MA10), the
lifecycle up to `completed` (MA11) and each side's "My engagements" page (MA13). The 48-hour expiry job (MA12)
is not built: an unanswered request stays `requested` (its `expires_at` is set, ready for MA12).
- **Backend:** models `CaProfile` + `CaVerificationStatus`, `CA_SPECIALIZATIONS`, `CA_LANGUAGES`,
  `CatalogService` + `ServiceUnit`, `CaService` in `app/models/marketplace.py`; schemas in `app/schemas/marketplace.py` (the list uses the shared
  `app/schemas/pagination.py`); logic in `app/services/marketplace_service.py`; routes in
  `app/routes/marketplace.py` (in `BLUEPRINTS`). Migrations
  `…_marketplace_add_ca_profiles.py`, `…_marketplace_add_service_catalog_and_ca_.py`,
  `…_marketplace_add_engagement_items_quoted_.py` (`engagement_items.quoted_price` + its CHECK).
  Engagement emails: `app/templates/email/engagement_{requested,accepted,quoted,declined}.txt` (the CA on a new
  request; the business when the CA accepts, quotes or declines).
- **Seed:** `seed_ca_profiles()` in `app/seed.py`: the demo CA gets a verified profile; four sample verified CAs
  (`sample-ca-1..4@demo.local`, cannot log in) fill the list. `seed_service_catalog()` adds the 13 catalog
  services (`SERVICE_CATALOG`); `seed_ca_prices()` gives the four sample CAs made-up prices (`SAMPLE_PRICES`), so
  ITR-3, ITR-4 and GSTR-3B reach three CAs and show a range. The demo CA gets no prices (set them on `/ca/services`).
  `SERVICE_FORM_CODES` fills `service_catalog.form_code` on every seed (existing rows too): the 9 filing
  services get their form (all three ITR services → `itr`); GST registration, tax audit, bookkeeping and notices
  stay empty.
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
  Engagements: the CA page has a "Request this CA" button → `pages/business/RequestCaPage.jsx` at
  `/business/marketplace/:caId/request` (tick filings, pick the service when the CA has several for one filing,
  total, send; blocked filings say why); `pages/business/MyEngagementsPage.jsx` at `/business/engagements`
  (business nav "My engagements": Quote to review / Waiting for the CA / Active / Finished; accept or reject a
  quote, withdraw); `pages/ca/CaEngagementsPage.jsx` at `/ca/engagements` (CA nav "My engagements": New requests
  / Active / Quote sent / Finished; accept, send a quote with a price per filing and a reason, decline, mark as
  completed). Both use `components/EngagementCard.jsx` (filings, listed / quoted / agreed prices and totals).
  Hooks `useRequestableFilings`, `sendRequest`, `useMyEngagements` (→ `null` before registration),
  `useCaEngagements`, `engagementAction(id, action, body)`; `ENGAGEMENT_STATUS_LABELS`; `lib/dates.js`
  (`formatDate`, `formatDateTime` in Indian time).
- **Tests:** `tests/test_marketplace_ca_profile.py`, `tests/test_marketplace_ca_list.py`,
  `tests/test_marketplace_services.py`, `tests/test_marketplace_ca_detail.py`,
  `tests/test_marketplace_engagements.py`, `tests/test_seed_command.py`; `CaProfilePage.test.jsx`,
  `CaServicesPage.test.jsx`, `MarketplacePage.test.jsx`, `CaDetailPage.test.jsx`, `TypicalFeesPage.test.jsx`,
  `RequestCaPage.test.jsx`, `MyEngagementsPage.test.jsx`, `CaEngagementsPage.test.jsx` (sample data in
  `test/engagementData.js`), `lib/money.test.js`.
- **Not yet:** MA12 (the expiry job and re-matching email), Certificate of Practice upload + OCR, the admin
  verify/reject screen, the admin catalog editor, CA capacity limits, pro-bono, ratings (a section on the CA
  page), the in-app notification tray (engagement news is email only).

## Tables
- `ca_profiles`: one CA's practice profile and verification status (details in `docs/DATA_MODEL.md`). The
  `schema: complete data model` migration added `pro_bono_slots_per_month` (≥ 0), `rejection_reason`,
  `verified_at`, `verified_by_id` (the admin) and `cop_document_id` (the Certificate of Practice document); no
  code uses them yet. The existing names stay: `about` is the bio, `capacity` the max active clients.
  `CaProfile.user` names its foreign key (`foreign_keys=[user_id]`) because the table now has two links to `users`.
- `service_catalog` (`CatalogService`): the standard services every CA prices against (seeded; config data). New
  `form_code`: the filing a service is for (seeded from `SERVICE_FORM_CODES`; null for services that are not one
  filing). A request uses it to find the CA's price for a filing.
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

| GET | `/api/v1/marketplace/cas/<id>/requestable-filings` | business | the business's filings, soonest due first: `{id, form_code, period_label, due_date, status, options: [{service_id, name, price}], blocked_reason}`; `options` are this CA's services for that form; `blocked_reason` is null, "Already filed.", "Already requested from a CA or with a CA." or "This CA has not listed a price for this filing." · 404 `CA_NOT_FOUND`, `BUSINESS_NOT_FOUND` |
| POST | `/api/v1/marketplace/engagements` | business | body `{ca_profile_id, items: [{compliance_item_id, service_id}]}` (at least one) → 201 the engagement (`requested`; `listed_price` copied from the CA's menu; `expires_at` = +48 h); the CA is emailed · 404 `CA_NOT_FOUND` / `FILING_NOT_FOUND`, 400 `DUPLICATE_FILING` / `SERVICE_NOT_OFFERED`, 409 `FILING_ALREADY_FILED` / `FILING_ALREADY_REQUESTED` |
| GET | `/api/v1/marketplace/my-engagements` | business | its engagements, newest first · 404 `BUSINESS_NOT_FOUND` |
| GET | `/api/v1/marketplace/ca-engagements` | ca | their engagements, newest first (empty without a profile) |
| POST | `/api/v1/marketplace/engagements/<id>/accept` | ca | `requested` → `active`; agreed = listed; the filings become "With CA"; the business is emailed |
| POST | `/api/v1/marketplace/engagements/<id>/quote` | ca | body `{reason, prices: [{engagement_item_id, price}]}` (a price 0 to 10,00,000 for every filing, 400 `QUOTE_INCOMPLETE` otherwise) → `quoted`; the business is emailed with the reason |
| POST | `/api/v1/marketplace/engagements/<id>/decline` | ca | `requested` → `declined`; the business is emailed |
| POST | `/api/v1/marketplace/engagements/<id>/complete` | ca | `active` → `completed` (no check that the filings are filed yet) |
| POST | `/api/v1/marketplace/engagements/<id>/accept-quote` | business | `quoted` → `active`; agreed = quoted; the filings become "With CA" |
| POST | `/api/v1/marketplace/engagements/<id>/reject-quote` | business | `quoted` → `cancelled` |
| POST | `/api/v1/marketplace/engagements/<id>/withdraw` | business | `requested` → `cancelled` |

Every engagement response is `{id, status, ca_profile_id, ca_name, business_name, quote_reason, requested_at,
expires_at, responded_at, activated_at, completed_at, items: [{id, compliance_item_id, form_code, period_label,
due_date, service_name, listed_price, quoted_price, agreed_price}]}`. Every action answers 404
`ENGAGEMENT_NOT_FOUND` for an engagement of another CA or business, and 409 `INVALID_STATUS` from the wrong
status.

`city` matches any part of the city name, any case. Money is sent as a string with two decimals (`"750.00"`).
Planned: admin verification and the service catalog under `/api/v1/admin/...`.

## Service functions other modules call
None yet. Planned: `has_active_engagement(ca_id, business_id)` (used by `ca_has_active_access`), `engagement_status_for(item_id)` (used by compliance).

## Depends on
core-auth (users, roles, `current_business()`), compliance (`list_filings`, `get_filings_by_ids`,
`mark_filings_with_ca`), onboarding (`get_business`), core-infra (`send_email`; the worker for the 48 h expiry,
MA12), documents (CoP upload, later).

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
