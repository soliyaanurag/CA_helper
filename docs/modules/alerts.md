# alerts: reminders, notification settings, penalty estimator

## Purpose
All scheduled user alerts (T-7/T-3/T-1 and overdue reminders by email + tray), per-type notification settings, and the dynamic penalty estimator shown on the dashboard and item page.

## What exists now
Skeleton only; no features yet.
- Backend: no code yet (no blueprint, models, schemas or services). Create `routes/alerts.py`, `schemas/alerts.py`, `services/alerts_service.py` (and `models/alerts.py`) when the first feature lands, and add the blueprint to `BLUEPRINTS` (docs/PATTERNS.md). The worker runs no alerts jobs yet.
- Frontend: one placeholder page, "Notification settings" at `/business/alerts` (business nav), `frontend/src/pages/business/AlertsPage.jsx`, built from `Placeholder`; no API hooks yet.

## Tables
Created by migration `schema: complete data model` (no service, route or page uses them yet). Columns, constraints and status values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/alerts.py`.
- `notifications`: the in-app tray (moved here from core-infra); soft-deleted when dismissed
- `notification_settings`: email on/off per user and type (no row = on)
- `reminder_log`: one row per filing and reminder kind, so a reminder is never sent twice
- `penalty_rules` (config): late fee per day, cap, interest rate, nil-return fee, `source_reference`, `effective_from/to`

## Endpoints
None yet. Planned: `/api/v1/alerts/...` (settings, penalty estimate).

## Service functions other modules call
None yet. Planned: `estimate_penalty(item_id)` (used by compliance).

## Depends on
core-infra (worker, email, notifications), compliance (items and due dates).

## Contracts (don't change without telling the team)
- Jobs added in `build_scheduler()` (`backend/worker.py`) with ids `alerts.*`

## Known issues
None yet.
