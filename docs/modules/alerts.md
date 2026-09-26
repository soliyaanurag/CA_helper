# alerts: reminders, notification settings, penalty estimator

## Purpose
All scheduled user alerts (T-7/T-3/T-1 and overdue reminders by email + tray), per-type notification settings, and the dynamic penalty estimator shown on the dashboard and item page.

## What exists now
Skeleton only; no features yet.
- Backend (`backend/app/modules/alerts/`): only `__init__.py` and `routes.py`, whose `alerts` blueprint is registered under `/api/v1` with no routes yet; no models, services or seed data; no `register_jobs`, so the worker runs no jobs; no tests yet.
- Frontend (`frontend/src/features/alerts/`): one placeholder page, "Notification settings" at `/business/alerts` (business nav), built from `ModulePlaceholder`; no API hooks yet.

## Tables
None yet. Planned:
- `reminder_log`: item + reminder kind + sent_at, for de-duplication
- `notification_settings`: user, type, email on/off
- `penalty_rules` (config): late fee/interest per form with `source_reference`, `effective_from/to`

## Endpoints
None yet. Planned: `/api/v1/alerts/...` (settings, penalty estimate).

## Service functions other modules call
None yet. Planned: `estimate_penalty(item_id)` (used by compliance).

## Depends on
core-infra (worker, email, notifications), compliance (items and due dates).

## Contracts (don't change without telling the team)
- Jobs registered via `register_jobs(scheduler)` with ids `alerts.*`

## Known issues
None yet.
