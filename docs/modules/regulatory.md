# regulatory: news monitor and admin approval

## Purpose
Scrapes configured news/official sources, uses Gemini to extract structured deadline/rule changes, matches affected users, and after one-click admin approval flags, emails and notifies them and raises their CAs' urgency.

## What exists now
Skeleton only; no features yet.
- Backend: no code yet (no blueprint, models, schemas or services). Create `routes/regulatory.py`, `schemas/regulatory.py`, `services/regulatory_service.py` (and `models/regulatory.py`) when the first feature lands, and add the blueprint to `BLUEPRINTS` (docs/PATTERNS.md). No scheduled jobs yet.
- Frontend: one placeholder page, "Regulatory news" at `/admin/regulatory` (admin nav), `frontend/src/pages/admin/RegulatoryAdminPage.jsx`, built from `Placeholder`; no API hooks yet.

## Tables
Created by migration `schema: complete data model` (no service, route or page uses them yet). Columns, constraints and status values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/regulatory.py`.
- `news_sources` (config), `news_articles` (unique url and content hash), `regulatory_changes` (extracted change, form codes, admin review)
- `regulatory_change_matches`: businesses affected by an approved change (N–N, notified time)

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
