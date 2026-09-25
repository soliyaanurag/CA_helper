# alerts: reminders, notification settings, penalty estimator

## Purpose
All scheduled user alerts (T-7/T-3/T-1 and overdue reminders by email + tray), per-type notification settings, and the dynamic penalty estimator shown on the dashboard and item page.

## What exists now
Skeleton only; no features yet.
- Backend (`backend/app/modules/alerts/`): the `alerts` blueprint is registered under `/api` with no routes; `models.py`, `schemas.py` and `services.py` are empty; `seed()` does nothing; no `register_jobs`, so the worker runs no jobs; `tests/` is empty.
- Frontend (`frontend/src/features/alerts/`): one placeholder page, "Notification settings" at `/app/alerts` (business nav), built from `ModulePlaceholder`; `api.ts` is empty.

## Tables
None yet. Planned:
- `reminder_log`: item + reminder kind + sent_at, for de-duplication
- `notification_settings`: user, type, email on/off
- `penalty_rules` (config): late fee/interest per form with `source_reference`, `effective_from/to`

## Endpoints
None yet. Planned: `/api/alerts/...` (settings, penalty estimate).

## Service functions other modules call
None yet. Planned: `estimate_penalty(item_id)` (used by compliance).

## Depends on
core-infra (worker, email, notifications), compliance (items and due dates).

## Contracts (don't change without telling the team)
- Jobs registered via `register_jobs(scheduler)` with ids `alerts.*`

## Known issues
None yet.
