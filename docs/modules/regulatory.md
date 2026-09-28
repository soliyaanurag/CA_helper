# regulatory: news monitor and admin approval

## Purpose
Scrapes configured news/official sources, uses Gemini to extract structured deadline/rule changes, matches affected users, and after one-click admin approval flags, emails and notifies them and raises their CAs' urgency.

## What exists now
The news monitor works end to end (RE1–RE6, the news part of X2).
- **Backend** (`services/regulatory_service.py`, `routes/regulatory.py`, `schemas/regulatory.py`; models in
  `models/regulatory.py`, no migration: the tables came with the data model):
  1. **Sources (RE1):** `news_sources`, seeded by `make seed` (`seed_news_sources`): TaxGuru GST feed and TaxGuru
     income-tax feed (RSS, on), CBIC GST home page (web page, off). Admins list, add (409 `SOURCE_EXISTS`) and switch
     them on or off.
  2. **Scan (RE2):** `scan_news()` for each enabled source: `robots.txt` first (`urllib.robotparser`, our user agent
     `CAHelperBot/1.0`; no robots.txt = allowed, any other error = skipped), then the download (15 s timeout,
     2 MB cap). RSS: the newest 30 items (title, link, date, description as plain text). Web page: every link whose
     text has 8+ words becomes an item. An article with a known URL or the same text (`content_hash`) is skipped.
     Only the standard library is used (`urllib`, `xml.etree`); no new package.
  3. **Extraction (RE3):** only an article naming one of our 7 forms (patterns like `gstr-3b`, `24q`, `itr`) **and**
     a change word (due date, last date, extended/extension, deadline, late fee, waiver, postpone) goes on, at most
     10 per run. Gemini (`app/utils/gemini_client.py`) returns JSON; everything is checked: unknown form codes,
     schemes, entity types and states are dropped, dates must be YYYY-MM-DD, an unknown type becomes `other`,
     `relevant: false` gives no change. Without Gemini (no key, 503, not JSON) a **keyword change** is saved: the
     title as summary, the forms named, `due_date_extension` only for "extended/extends", no dates,
     `affected_categories.extracted_by = "keywords"`. Every change starts `pending`: nobody is told.
  4. **Review (RE4):** `list_changes(status)` (with article title, URL, source, publish time, match count),
     `approve_change`, `reject_change` (404 `CHANGE_NOT_FOUND`, 409 `CHANGE_NOT_PENDING`); `reviewed_at`,
     `reviewed_by_id` record who decided.
  5. **Who is told (RE5):** on approval, the live businesses with a live **not-filed** filing of one of the forms
     (`compliance_service.business_ids_with_open_filings`) whose GST scheme, entity type and state fit the change's
     lists (`onboarding_service.business_categories`; a missing list = everyone) get a
     `regulatory_change_matches` row, a tray entry and an email (`alerts_service.notify`, type
     `regulatory_update`, link `/business/compliance`; the email can be switched off). Their CAs with an ACTIVE
     engagement get a tray entry linking to `/ca/clients/{business}`, and for 30 days the client's urgency gets
     15 points (`active_changes_for` → `ca_workspace_service.regulatory_points`). Filings and due dates are **not**
     changed: that stays an admin/data task.
  6. **Manual run (RE6):** `conda run -n ca-helper --cwd backend flask --app app regulatory scan`, or "Scan now" on
     the admin page (`POST /admin/regulatory/scan`, 2 per minute).
  - **Worker (X2):** `regulatory.scan_news` every day at 07:00 IST (`backend/worker.py`).
- **Frontend:** `pages/admin/RegulatoryAdminPage.jsx` (`/admin/regulatory`, nav "Regulatory news"): tabs "To review"
  (a card per change: type, forms, "Found by keywords (no AI): read the article" when so, summary, article link,
  who it is for, period and dates, **Approve and notify** / **Reject**), "Reviewed" (approved with how many
  businesses were told, rejected), "Sources" (switch on/off, **Scan now** with the counts, add a source).
  `api/regulatory.js`.
- **Tests:** `tests/test_regulatory_monitor.py` (seeded sources, add/switch off, scan saves once, robots.txt,
  disabled/broken source, web-page links, Gemini extraction, unknown values dropped, irrelevant, keyword fallback,
  "request for extension" is `other`, admin list, approval tells the business (tray + email) and its CA, urgency
  points, 30-day window, another state tells nobody, filed filings not affected, reject + reviewed once, admin
  only, scan now, CLI, worker job), frontend `RegulatoryAdminPage.test.jsx`. The network is never used in tests
  (`_download` is faked).

### How a change is extracted (AI first, keywords only as a fallback)
Order for every new article (`_looks_relevant` → `_extract_change` in `regulatory_service.py`):
1. **Keyword filter, always first:** the title + description must contain one of our forms **and** a change word,
   else the article is only stored (no Gemini call, no change). Forms (`FORM_PATTERNS`, any case): `GSTR-1`/`GSTR 1`,
   `GSTR-3B`, `CMP-08`, `GSTR-4`, `24Q`, `26Q`, `ITR`/`ITRs`/`income tax return(s)`. Change words (`CHANGE_WORDS`):
   due date, last date, extend, extension, deadline, late fee, waive, waiver, postpone. At most 10 per scan.
2. **Gemini** reads it and answers JSON. A JSON answer is used as it is (after the checks above): a change, or
   `relevant: false` = **no change** (the keyword version is *not* used then).
3. **Keyword version only if Gemini fails:** no key, an error such as 503 "high demand" after 3 tries, a timeout
   (20 s), or a reply that is not JSON. It is built by fixed rules (`_change_from_keywords`):

   | Field | Rule |
   |---|---|
   | summary | the article title, as published |
   | form_codes | every form from the list above found in the text |
   | change_type | `due_date_extension` only if the text says "extended" or "extends"; else `other` |
   | dates | none (a pattern cannot read dates reliably, so nothing is guessed) |
   | affected_categories | `{"extracted_by": "keywords"}`: everyone with an open filing of those forms |

   The admin page shows it with the badge **"Found by keywords (no AI): read the article"**: open the article
   before approving, and reject requests, opinions or anything too broad.

## Tables
Columns, constraints and status values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/regulatory.py`.
- `news_sources` (config, seeded), `news_articles` (unique url and content hash), `regulatory_changes` (the
  extracted change, admin review)
- `regulatory_change_matches`: businesses told about an approved change (N–N, notified time)

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/v1/admin/regulatory/changes?status=` | admin | `[{id, change_type, summary, form_codes, affected_categories, dates, status, created_at, reviewed_at, article_title, article_url, published_at, source_name, match_count}]`, newest first, at most 100 |
| POST | `/api/v1/admin/regulatory/changes/{id}/approve` | admin | the change, `approved`, `match_count` = businesses told · 404 `CHANGE_NOT_FOUND` · 409 `CHANGE_NOT_PENDING` |
| POST | `/api/v1/admin/regulatory/changes/{id}/reject` | admin | the change, `rejected` · 404 · 409 |
| GET | `/api/v1/admin/regulatory/sources` | admin | `[{id, name, url, kind, enabled}]` |
| POST | `/api/v1/admin/regulatory/sources` | admin | body `{name, url, kind: "rss" \| "html"}` → 201 the source · 409 `SOURCE_EXISTS` |
| PUT | `/api/v1/admin/regulatory/sources/{id}` | admin | body `{enabled}` → the source · 404 `SOURCE_NOT_FOUND` |
| POST | `/api/v1/admin/regulatory/scan` | admin | `{sources, blocked_by_robots, failed, new_articles, changes}` · 429 (2 per minute) |

## Service functions other modules call
- `active_changes_for(business_id, today=None) -> list[RegulatoryChange]`: approved changes that affected the
  business in the last 30 days (ca_workspace urgency).
- `forms_text(form_codes) -> str`: e.g. "GSTR-3B, GSTR-1".
- `scan_news() -> dict`: the worker job and the CLI.

## Depends on
core-infra (worker, Gemini client), compliance (`business_ids_with_open_filings`), onboarding
(`business_categories`), alerts (`notify`), marketplace (`active_cas_of_business`), core-auth (`get_active_user`).

## Contracts (don't change without telling the team)
- Scraper respects robots.txt; nothing is sent to users before admin approval

## Known issues
- An article is sent to Gemini only in the run that first saves it: if Gemini is down then, the keyword change is
  kept and the article is not asked again (the admin reads it before approving).
- The keyword fallback cannot tell who is affected, so a keyword change reaches everyone with an open filing of
  those forms; read the article and reject it if it is too broad.
- Approving a due-date extension does not move any due date; the obligation templates stay the source of due dates.
- TaxGuru titles start with the category ("Income Tax | ..."); they are kept as published.
- A reply from Gemini that starts like JSON but is broken is treated as "not a change" instead of falling back to
  the keyword version (rare; possible follow-up).
- Possible follow-up: on the next scan, ask Gemini again for keyword-only changes that are still pending.
