# regulatory: news monitor and admin approval

## Purpose
Scrapes configured news/official sources, uses Gemini to extract structured deadline/rule changes, matches affected users, and after one-click admin approval flags, emails and notifies them and raises their CAs' urgency.

## What exists now
Skeleton only; no features yet.
- Backend (`backend/app/modules/regulatory/`): only `__init__.py` and `routes.py`, whose `regulatory` blueprint is registered under `/api/v1` with no routes yet; no models, services or seed data; no scheduled jobs; no tests yet.
- Frontend (`frontend/src/features/regulatory/`): one placeholder admin screen, "Regulatory news" at `/admin/regulatory` (admin nav, from `admin/`), built from `ModulePlaceholder`; no API hooks yet.

## Tables
None yet. Planned:
- `news_sources` (config), `news_articles`, `regulatory_changes` (extracted change + approval status)

## Endpoints
None yet. Planned: admin approval at `/api/v1/admin/regulatory/...`.

## Service functions other modules call
None yet. Planned: `active_changes_for(business_id)` (used by ca_workspace urgency).

## Depends on
core-infra (worker, Gemini wrapper, email, notifications), onboarding (profiles for matching).

## Contracts (don't change without telling the team)
- Scraper respects robots.txt; nothing is sent to users before admin approval

## Known issues
None yet.
