# alerts: reminders, notification settings, penalty estimator

## Purpose
All scheduled user alerts (T-7/T-3/T-1 and overdue reminders by email + tray), per-type notification settings, and the dynamic penalty estimator shown on the dashboard and item page.

## Owner
Member B (Infrastructure, documents & AI)

Folders: `backend/app/modules/alerts/`, `frontend/src/features/alerts/`

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [ ] ALR-01 · P1 · B · Daily job: reminder email + tray entry for items due in 7 days
- [ ] ALR-02 · P2 · B · Full reminder schedule (T-7/T-3/T-1 + overdue) with de-duplication
- [ ] ALR-03 · P2 · B · Notification settings page (per-type email on/off)
- [ ] ALR-04 · P3 · B · Dynamic penalty estimator (rules from rule tables, daily recompute, shown on dashboard + item page)

## Tables owned
- `reminder_log` (planned): item + reminder kind + sent_at, for de-duplication
- `notification_settings` (planned): user, type, email on/off
- `penalty_rules` (planned config): late fee/interest per form with `source_reference`, `effective_from/to`

## Endpoints exposed
Planned: `/api/alerts/...` (settings, penalty estimate).

## Service functions others may call
- Planned: `estimate_penalty(item_id)` (used by compliance)

## Depends on
core-infra (worker, email, notifications), compliance (items and due dates).

## Contracts others rely on
- Jobs registered via `register_jobs(scheduler)` with ids `alerts.*`

## Known issues
_None yet._

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0: created this doc and its task list.
