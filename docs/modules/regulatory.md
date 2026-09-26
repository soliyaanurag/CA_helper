# regulatory: news monitor and admin approval

## Purpose
Scrapes configured news/official sources, uses Gemini to extract structured deadline/rule changes, matches affected users, and after one-click admin approval flags, emails and notifies them and raises their CAs' urgency.

## What exists now
Skeleton only; no features yet.
- Backend: no code yet (no blueprint, models, schemas or services). Create `routes/regulatory.py`, `schemas/regulatory.py`, `services/regulatory_service.py` (and `models/regulatory.py`) when the first feature lands, and add the blueprint to `BLUEPRINTS` (docs/PATTERNS.md). No scheduled jobs yet.
- Frontend: one placeholder page, "Regulatory news" at `/admin/regulatory` (admin nav), `frontend/src/pages/admin/RegulatoryAdminPage.jsx`, built from `Placeholder`; no API hooks yet.

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
