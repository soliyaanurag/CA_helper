# regulatory: news monitor and admin approval

## Purpose
Scrapes configured news/official sources, uses Gemini to extract structured deadline/rule changes, matches affected users, and after one-click admin approval flags, emails and notifies them and raises their CAs' urgency.

## Owner
Member B (Infrastructure, documents & AI)

Folders: `backend/app/modules/regulatory/`, `frontend/src/features/regulatory/` (admin screen in `admin/`)

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [ ] REG-01 · P3 · B · News scraper (configured sources, respects robots.txt, de-dup, stored articles)
- [ ] REG-02 · P3 · B · Gemini extraction of structured change (type, forms, categories, dates)
- [ ] REG-03 · P3 · B · Affected-user matching + admin approval screen
- [ ] REG-04 · P3 · B · On approval: flag users, email, tray entry, urgency input for CAs
- [ ] REG-05 · P4 · B · Additional news/official sources
- [ ] REG-06 · P5 · B · Extraction precision evaluation (~20 real items)

## Tables owned
- `news_sources` (planned config), `news_articles` (planned), `regulatory_changes` (planned: extracted change + approval status)

## Endpoints exposed
Planned: admin approval at `/api/admin/regulatory/...`.

## Service functions others may call
- Planned: `active_changes_for(business_id)` (used by ca_workspace urgency)

## Depends on
core-infra (worker, Gemini wrapper, email, notifications), onboarding (profiles for matching).

## Contracts others rely on
- Scraper respects robots.txt; nothing is sent to users before admin approval

## Known issues
_None yet._

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0: created this doc and its task list.
