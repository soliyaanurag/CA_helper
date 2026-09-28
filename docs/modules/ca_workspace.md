# ca_workspace: CA multi-client dashboard and client workspace

## Purpose
The CA's multi-client dashboard with urgency scores, the deadline batch view, and the client workspace (profile, calendar, vault, document requests, mark filed, private notes).

## What exists now
My clients with urgency (CW2, CW6), the client workspace (CW3), document requests (CW4), the CA marking a filing
filed (CW5) and the deadline batch view (CW7). Not yet: private notes (`ca_notes`), bulk document requests,
inviting existing clients.
- **Backend** (`services/ca_workspace_service.py`, `routes/ca_workspace.py`, `schemas/ca_workspace.py`; model
  `models/ca_workspace.py`):
  - A CA works only on the filings of their **active** engagements (`marketplace_service.active_work()`). Every
    route that names a business starts with `require_ca_access(business_id)` (404 `BUSINESS_NOT_FOUND`); with two
    CAs on one business, each sees only their own filings.
  - **My clients (CW2):** `list_clients(user, today)`: one row per business with an active engagement: engaged
    and still-open filings, next deadline, overdue count, missing required documents, open requests, and the
    urgency, most urgent first.
  - **Urgency (CW6):** a weighted sum with a reason per part: `POINTS_PER_OVERDUE_FILING` (40 each),
    `POINTS_DUE_WITHIN_3_DAYS` (25) or `POINTS_DUE_WITHIN_7_DAYS` (10) for the next deadline,
    `POINTS_PER_MISSING_DOCUMENT` (5 per required checklist entry not ticked), `POINTS_PER_OPEN_REQUEST` (3).
    **Hook:** `regulatory_points(business_id) -> [{reason, points}]` returns `[]`; the regulatory module fills it
    (approved changes that affect the business).
  - **Client workspace (CW3):** `get_client(user, business_id)`: the business and its profile (full, as the
    access rules allow during active work), and the CA's engaged filings, each with its checklist (ticks), its
    files and acknowledgement (`documents_service.documents_by_filing`) and its open document requests. The CA
    opens a file with `GET /api/v1/documents/{id}/file` (documents module, `ca_can_access_document`).
  - **Document requests (CW4):** the CA asks for one checklist entry (or `general`) of an engaged, not-filed
    filing, with a message; the business owner gets a tray entry and an email (`document_request`, can be
    switched off) linking to the filing page. The business sees open requests (from **active** engagements only)
    on its dashboard to-do list and the filing page, and answers with a vault file (uploading it first if
    needed): `fulfil_document_request` links the file to the filing under the requested key
    (`documents_service.attach_document`, which also ticks the entry), marks the request `fulfilled` and tells the
    CA (tray + email, link `/ca/clients/{business}`). The CA can cancel an open request.
  - **Mark filed (CW5):** `mark_filed_for_client` → `compliance_service.mark_filed_by_ca()` (only a `with_ca`
    filing; status `filed`, path `ca`; the acknowledgement is owned by the business owner, uploaded by the CA),
    cancels the filing's open requests, tells the business (tray + email) and, when it was the engagement's last
    filing, **completes the engagement** (`marketplace_service.complete_if_all_filed`). The CA's "Mark as
    completed" on My engagements still works. The business sees the filing as filed with the acknowledgement on its
    filing page, and cannot undo it (`NOT_SELF_FILED`).
  - **Batches (CW7):** `list_batches(user, today)`: the CA's engaged, not-filed filings grouped by due date and
    form, each client's readiness (required ready / total, missing labels).
- **Frontend:**
  - `pages/ca/CaWorkspacePage.jsx` (`/ca/clients`, nav "My clients"): a card per client, urgency badge, next
    deadline, counts and "Why flagged" (each reason with its points).
  - `pages/ca/CaClientPage.jsx` (`/ca/clients/:businessId`): profile card; per filing: status, checklist
    progress, files (Open), requests waiting for the client (Cancel request), "Ask for a document" (entry +
    message; defaults to the first entry not ticked) and, for a `with_ca` filing, "Mark as filed" (ARN + file).
  - `pages/ca/CaBatchesPage.jsx` (`/ca/batches`, nav "Deadline batches"): one card per form and due date, a row
    per client with its readiness.
  - Business: `FilingPage` "Your CA asked for documents" card (upload a file or choose one from the vault, "Send
    to my CA"); `BusinessDashboardPage` lists each open request first in "To do".
  - `api/caWorkspace.js`: `useCaDashboard`, `useCaClients`, `useCaClient`, `useCaBatches`,
    `createDocumentRequest`, `cancelDocumentRequest`, `caMarkFiled`, `useMyDocumentRequests`,
    `fulfilDocumentRequest`, `CA_WORKSPACE_KEY`.
- **Tests:** backend `test_ca_workspace_clients.py` (clients and urgency, sorting, only active work, roles, the
  workspace and its access, requests with the tray entry and email, checks, cancel, fulfil and the CA opening the
  file, another business, CA mark filed with the acknowledgement, completing the engagement, checks, batches),
  `test_ca_workspace_dashboard.py`; frontend `CaWorkspacePage.test.jsx`, `CaClientPage.test.jsx`,
  `CaBatchesPage.test.jsx`, the "documents the CA asked for" tests in `FilingPage.test.jsx`, the request to-do in
  `BusinessDashboardPage.test.jsx`.

## Tables
Created by migration `schema: complete data model`; no migration in this module. Columns, constraints and status
values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/ca_workspace.py`.
- `document_requests` **(used, CW4)**: a CA's request for one document for one filing of an engagement:
  `open → fulfilled` (with `document_id`, `fulfilled_at`) or `cancelled` (by the CA, or when the CA marks the
  filing filed)
- `ca_notes`: a CA's private notes per client; soft delete (no code yet)

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| GET | `/api/v1/ca-workspace/dashboard` | ca | `{message}` (welcome text) |
| GET | `/api/v1/ca-workspace/clients` | ca | `[{business_id, business_name, filing_count, open_filing_count, open_request_count, next_deadline, overdue_count, missing_documents, score, reasons: [{reason, points}]}]`, most urgent first · 404 `CA_PROFILE_NOT_FOUND` |
| GET | `/api/v1/ca-workspace/clients/{business_id}` | ca (active engagement) | `{business, profile, filings: [{filing, checklist, documents: [{document_id, original_filename, doc_type, size_bytes, created_at, checklist_key}], open_requests}]}` · 404 `BUSINESS_NOT_FOUND` |
| POST | `/api/v1/ca-workspace/clients/{business_id}/document-requests` | ca (active engagement) | body `{compliance_item_id, checklist_key="general", message}` → 201 the request · 404 `BUSINESS_NOT_FOUND`, `FILING_NOT_FOUND` · 409 `FILING_LOCKED` · 422 `UNKNOWN_CHECKLIST_KEY` |
| POST | `/api/v1/ca-workspace/clients/{business_id}/filings/{item_id}/mark-filed` | ca (active engagement) | multipart `acknowledgement_no?`, `file?` → `{compliance_item_id, status, acknowledgement_no, engagement_completed}` · 404 · 409 `ALREADY_FILED`, `FILING_NOT_WITH_CA` · 400 storage errors |
| GET | `/api/v1/ca-workspace/batches` | ca | `[{form_code, due_date, ready_count, filings: [{business_id, business_name, compliance_item_id, period_label, status, required_total, required_ready, missing, ready}]}]` |
| POST | `/api/v1/ca-workspace/document-requests/{id}/cancel` | ca | the request, `cancelled` · 404 `REQUEST_NOT_FOUND` · 409 `REQUEST_NOT_OPEN` |
| GET | `/api/v1/ca-workspace/document-requests?compliance_item_id=` | business | its open requests (active engagements), oldest first, each with `ca_name` |
| POST | `/api/v1/ca-workspace/document-requests/{id}/fulfil` | business | body `{document_id}` → the request, `fulfilled` · 404 `REQUEST_NOT_FOUND`, `DOCUMENT_NOT_FOUND` · 409 `REQUEST_NOT_OPEN`, `FILING_LOCKED` |

A request: `{id, compliance_item_id, form_code, period_label, checklist_key, message, status, created_at,
fulfilled_at, document_id}`.

## Service functions other modules call
- `regulatory_points(business_id) -> [{reason, points}]`: **for the regulatory module to fill** (extra urgency).

## Depends on
marketplace (`active_work`, `active_cas_of_business`, `complete_if_all_filed`, `own_profile_id`,
`require_ca_access`), compliance (`get_filings_by_ids`, `checklist_with_ticks`, `checklist_progress`,
`checklist_keys`, `mark_filed_by_ca`, `DONE_STATUSES`, `FORM_FOLDERS`), documents (`documents_by_filing`,
`attach_document`, `GENERAL_KEY`), onboarding (`get_business`, `get_my_business`), alerts (`notify`),
regulatory (urgency input, later).

## Contracts (don't change without telling the team)
- Every read of client data goes through `ca_has_active_access` (rule 5): start each CA route with
  `require_ca_access(business_id)` (`app/utils/decorators.py`) and show only the filings of the CA's active
  engagements and documents allowed by `ca_can_access_document(...)` (marketplace, MA14)
- A fulfilled request's file is linked to the filing (`compliance_item_documents`), which is how the CA may open it
- Urgency weights are the named constants in `ca_workspace_service.py`; `regulatory_points()` is the regulatory hook

## Known issues
- No bulk document requests from the batch view yet, no private notes, no client invites.
- The CA cannot upload files other than the acknowledgement (clients send documents).
- A client whose filings are all filed stays in "My clients" until the engagement completes (it completes
  automatically when the CA marks the last filing).
