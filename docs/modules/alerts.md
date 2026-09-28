# alerts: reminders, notification settings, penalty estimator

## Purpose
All scheduled user alerts (T-7/T-3/T-1 and overdue reminders by email + tray), per-type notification settings, and the dynamic penalty estimator shown on the dashboard and item page.

## What exists now
The notification tray with the bell (AL1), email settings (AL3), the daily reminders (AL2), the penalty rules (AL4,
every amount still empty) and the estimator on the filing page and the dashboard (AL5).
- **Backend** (`services/alerts_service.py`, `routes/alerts.py`, `schemas/alerts.py`; model `models/alerts.py`):
  - **`notify(user, type, title, body, link=None, email=False)`** adds a tray entry (does not commit). With
    `email=True` it also emails `notification.txt`, unless the user switched that type off. The email is **queued
    on the database session and sent only after the caller's commit succeeds** (`queue_email()` plus two SQLAlchemy
    session listeners at the bottom of the service; a rollback drops the queue). So a service still commits once,
    and nobody is emailed about something that was not saved.
  - Tray: `list_notifications` (newest first, paginated), `unread_count`, `mark_read` (own entries only, 404
    `NOTIFICATION_NOT_FOUND`), `mark_all_read`. Every role has a tray.
  - Settings (AL3): `CONFIGURABLE_TYPES` = `deadline_reminder`, `overdue`, `document_request`,
    `regulatory_update` (email on/off; no row = on). `engagement_update` and `account` are always emailed
    (`ALWAYS_EMAILED_TYPES`): marketplace and auth send those emails themselves. Tray entries are always created.
  - Reminders (AL2): `send_reminders(today)` looks at every live, not-filed filing due within 7 days or already
    late. Windows (`REMINDER_WINDOWS`): 4–7 days before → `t_minus_7`, 2–3 → `t_minus_3`, 0–1 → `t_minus_1`, after
    the due date → `overdue`. Only the current window's reminder is sent, each kind once per filing
    (`reminder_log`). A filing **due before the business registered** gets none. The owner (and the CA of an
    **active** engagement on that filing, `marketplace_service.active_ca_users_by_filing`, linked to
    `/ca/clients/{business}`) gets a tray entry per
    filing; each person then gets **one summary email per run** (`reminders.txt`) listing the reminders whose type
    they have not switched off. Inactive or deleted users get nothing.
  - Penalties (AL5): `estimate_penalty(business, item_id, tax_due)` uses the `penalty_rules` row in force on the
    filing's **due date**: late fee = `flat_late_fee` if set, else days late × `late_fee_per_day` (or
    `nil_return_late_fee_per_day` for a nil return), capped at `max_late_fee`; interest = tax due ×
    `annual_interest_rate` % × days late / 365, only when the business enters the tax due. An empty (NULL) amount is
    skipped and `notes` say what is missing; `status` is `not_late`, `filed`, `estimated` or `pending`.
    `penalty_exposure(business)` adds the late fees of all overdue (late, not filed) filings; interest is not
    included (it needs each filing's tax). `label` is "Estimate (rules pending verification)" while a rule is
    `TODO_VERIFY`.
  - `seed.py`: `seed_penalty_rules()` adds one rule per form (7 rows), **every amount NULL**, `TODO_VERIFY` in
    `source_reference`, effective from 1 April 2025.
- **Worker:** `alerts.reminders` runs `send_reminders` every day at 08:15 IST (`backend/worker.py`). On demand, for
  demos: `conda run -n ca-helper --cwd backend flask --app app alerts send-reminders [--date 2026-10-06]` (`--date`
  runs it as if it were that day; what it records counts as sent).
- **Frontend:**
  - `components/NotificationBell.jsx` in the `AppShell` sidebar (every role): unread count (refreshed every
    minute), a tray with the latest 10 entries; clicking one marks it read and opens its `link`; "Mark all read".
  - `components/NotificationSettings.jsx`: a checkbox per configurable type, then "CA request update: always
    emailed" / "Account: always emailed". Pages `pages/business/AlertsPage.jsx` (`/business/alerts`) and
    `pages/ca/CaAlertsPage.jsx` (`/ca/alerts`, CA nav "Notification settings").
  - `FilingPage`: a "Late fees and interest" card for an overdue, not-filed filing (days late, late fee, interest,
    total, notes, an optional "Tax due (₹)" field). `BusinessDashboardPage`: a "Penalty exposure" card when there
    are overdue filings. Both show the label.
  - `api/alerts.js`: `useUnreadCount`, `useNotifications`, `markNotificationRead`, `markAllNotificationsRead`,
    `useNotificationSettings`, `saveNotificationSettings`, `usePenaltyEstimate`, `usePenaltyExposure`;
    `NOTIFICATION_TYPE_LABELS` in `lib/labels.js`.
- **Tests:** backend `test_alerts_notifications.py` (notify, email only after the commit, rollback, settings, tray
  endpoints for every role, own entries only), `test_alerts_reminders.py` (windows, once per kind, catch-up, one
  summary email, before registration, filed, switched off, deactivated owner, the active CA, worker job, CLI),
  `test_alerts_penalties.py` (seeded rules, pending, cap, nil return, flat fee, interest, rule by due date, not late /
  filed, exposure, endpoints, access), the AL1 section of `test_marketplace_engagements.py`; frontend
  `NotificationBell.test.jsx`, `AlertsPage.test.jsx`, the penalty tests in `FilingPage.test.jsx` and
  `BusinessDashboardPage.test.jsx`.

## Tables
Columns, constraints and status values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/alerts.py`.
- `notifications`: the in-app tray; soft-deleted when dismissed (no dismiss button yet)
- `notification_settings`: email on/off per user and configurable type (no row = on)
- `reminder_log`: one row per filing and reminder kind, so a reminder is never sent twice
- `penalty_rules` (config): late fee per day, cap, **flat late fee** (new), interest rate, nil-return fee, all
  nullable (migration `alerts: nullable penalty amounts and flat late fee`); `source_reference`,
  `effective_from/to`

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/v1/alerts/notifications?page=&page_size=` | any logged-in | `{items: [{id, type, title, body, link, read_at, created_at}], page, page_size, total}`, newest first |
| GET | `/api/v1/alerts/notifications/unread-count` | any logged-in | `{unread}` |
| POST | `/api/v1/alerts/notifications/{id}/read` | any logged-in | the entry, `read_at` set · 404 `NOTIFICATION_NOT_FOUND` (not yours) |
| POST | `/api/v1/alerts/notifications/read-all` | any logged-in | `{unread: 0}` |
| GET | `/api/v1/alerts/settings` | business, ca | `{items: [{type, email_enabled}] (the 4 configurable types), always_emailed: ["engagement_update", "account"]}` |
| PUT | `/api/v1/alerts/settings` | business, ca | body `{items: [{type, email_enabled}]}` → the settings · 422 for a type that is always emailed |
| GET | `/api/v1/alerts/penalties` | business | `{total_late_fees, overdue_count, estimated_count, pending_count, label, items: [estimate]}` · 404 `BUSINESS_NOT_FOUND` |
| GET | `/api/v1/alerts/penalties/{item_id}?tax_due=` | business | `{compliance_item_id, form_code, period_label, due_date, days_late, status, late_fee, interest, total, notes, label}` (amounts are strings or null) · 404 `BUSINESS_NOT_FOUND`, `FILING_NOT_FOUND` · 422 negative `tax_due` |

## Service functions other modules call
- `notify(user, type, title, body, link=None, email=False) -> Notification` (does not commit; call it before your
  commit). Used by marketplace (engagement events, `email=False`: it sends its own emails) and ca_workspace
  (document requests, "your CA filed it", `email=True`). Also regulatory (an approved change: the business owner `email=True`, its active CAs tray only).
- `queue_email(to, subject, template, **context)`: send an email only once the transaction commits.

## Depends on
core-infra (worker, email), compliance (`list_unfiled_filings_due_by`, `get_filings_by_ids`, `list_filings`,
`FORM_FOLDERS`, `DONE_STATUSES`), onboarding (`get_business`), marketplace (`active_ca_users_by_filing`).
alerts ↔ marketplace import each other's service modules (`from app.services import ...`); that works because
neither uses the other while it is being imported. Keep it that way (no `from ... import notify`).

## Contracts (don't change without telling the team)
- Jobs added in `build_scheduler()` (`backend/worker.py`) with ids `alerts.*` (`alerts.reminders`)
- `notify()` signature and "does not commit"; tray `link` is an app path (`/business/...`, `/ca/...`)
- Which types are configurable (`CONFIGURABLE_TYPES`): engagement and account emails are always sent
- Every penalty figure is shown with its `label`; a NULL amount is never treated as 0

## Known issues
- **Every penalty amount is NULL (`TODO_VERIFY`)**, so every estimate is "pending" until someone fills the rules
  from official sources (`docs/TODO_VERIFY.md`, "Penalties"). The ITR's fixed fee goes in `flat_late_fee`.
- GST late fees and caps that depend on turnover, and fees that differ for CGST/SGST, cannot be expressed: one
  rule per form and period. Interest needs the tax due, which we do not store.
- No "dismiss" for tray entries yet (the column exists).
- `--date` in the CLI records reminders as sent for that day; use it on demo data only.
