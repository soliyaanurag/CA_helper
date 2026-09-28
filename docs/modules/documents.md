# documents: encrypted vault and filing-proof OCR

## Purpose
Encrypted upload/download of documents (acknowledgements, checklist documents), the vault organised by FY/period/type, filing-proof OCR (ARN/ack number, date, period → Filed–verified) and document-type verification.

## What exists now
The vault (DO2–DO7): upload, list with filters, download, soft delete, and links between documents and filings
(per checklist entry). Local OCR (B2): every upload is read (ON12), acknowledgements verify filings (DO8) and files
that look like another type are flagged (DO9).
- **Encrypted storage** (core-infra): `app/utils/storage.py` `save_file(data, mime_type)` checks the type by the
  file's first bytes (PDF, JPG, PNG only) and the size (`MAX_UPLOAD_MB`), encrypts with Fernet and writes it to
  `UPLOAD_DIR` (default `backend/instance/uploads`, gitignored) under a random key; `open_file(key)`,
  `delete_file(key)`. Tests: `tests/test_storage.py`.
- **Backend** (`services/documents_service.py`, `routes/documents.py`, `schemas/documents.py`):
  - `add_document(owner_id, uploaded_by_id, upload, doc_type)` stores the file, adds and flushes the `documents`
    row (name, type, size, SHA-256; no commit), then calls **`on_document_uploaded(document, data)`**. Every upload
    goes through it: vault, acknowledgement (compliance), Certificate of Practice (marketplace).
  - **`on_document_uploaded(document, data)` (ON12):** reads the file locally (`utils/ocr.py`) and stores only
    non-personal facts in `ocr_fields` (`utils/document_text.read_proof_fields`: `acknowledgement_no`,
    `filing_date`, `form_codes`, `months`, `months_with_year`, `financial_years`, `quarters`, `type_guess`), with
    `ocr_status` `processed`; an unreadable file gets `failed` and `{"error": "..."}`. The text, PAN, GSTIN and
    names are never stored (rule 4). OCR never makes an upload fail. No commit.
  - **Type check (DO9):** `type_warning(document)` is the guessed type when it differs from the uploaded type
    (never for `other`); every listed document has `type_warning` (null when fine). The vault shows "Looks like:
    Bank statement" under the type.
  - **Proof of filing (DO8):** `verify_acknowledgement(document, filing) -> {verified, problems,
    acknowledgement_no, filing_date}`: the file must name the form, show the period (a month: its name with the
    financial year, or "092026"; a quarter: the financial year with "Q2" or one of its months; a year: the financial
    year, or for ITR the assessment year after it), have a number (equal to the typed one, if any) and a filing date
    on or after the period's end. Used by compliance when a filing is marked filed (CO10).
  - Upload (DO2): type (any `DocumentType` but `certificate_of_practice`), optional `fy` (`2026-27`) and
    `period_label`. With `compliance_item_id` (+ `checklist_key`, default `general`) the same request links the file
    to that filing; the link is checked **before** the file is stored, and a linked file without its own FY or
    period gets the filing's.
  - List (DO3): the business owner's live documents, newest first, paginated; filters `fy`, `doc_type` and
    `compliance_item_id` (the files linked to that filing plus its acknowledgement). Each document lists its
    `links` (filing, form, period, checklist key) and `acknowledgement_of` (the filings it is the acknowledgement of).
  - Download (DO4, DO7): `get_document_file(user, document_id)` decrypts on the fly for the **owner**, or for a
    **CA** when `marketplace_service.ca_can_access_document()` allows it (a file linked to, or the acknowledgement
    of, a filing in the CA's **active** engagement). Anyone else gets 404 `DOCUMENT_NOT_FOUND`; admins are not
    allowed on the route (403), they never read contents.
  - Delete (DO5): soft delete, and its links to open filings are deleted. 409 `DOCUMENT_IN_USE` when it is a
    filing's acknowledgement ("Undo 'mark as filed'") or linked to a `filed` / `filed_verified` filing; the message
    names the filing.
  - Links (DO6): `compliance_item_documents`, one row per filing + document + checklist key (`general` when it
    answers no entry); one file can serve several filings; linking twice changes nothing. **Linking to a checklist
    entry ticks it** (and the status moves as with a manual tick, `compliance_service.tick_checklist_entry`);
    unlinking deletes the row and leaves the tick. Once a filing is filed its links are fixed: 409 `FILING_LOCKED`
    for link, upload-and-link and unlink. A business may still add files while its filing is `with_ca`.
- **Frontend:**
  - `pages/business/DocumentsPage.jsx` (`/business/documents`, nav "Document vault"): upload card (file, type,
    financial year, period), filters (financial year, type, filing), a table (file, type, year / period, size,
    uploaded, "Used for" with links to the filing pages, Open, Delete with a confirmation), Previous / Next pages.
  - `FilingPage` checklist: under each entry its linked files (Open, Remove) and "Add a file" (upload a new file,
    or link one from the vault); "Other documents for this filing" for `general` links. Only Open once filed.
  - `api/documents.js`: `useDocuments(params)`, `uploadDocument`, `deleteDocument`, `linkDocument`,
    `unlinkDocument`, `downloadDocument` (saves the file under its name), `UPLOAD_TYPES`, `DOCUMENTS_KEY`;
    `DOCUMENT_TYPE_LABELS` in `lib/labels.js`.
- **Tests:** backend `test_documents_vault.py` (upload and its checks, OCR hook, list filters and pages, by filing
  with the acknowledgement, own documents only, download decrypts, CA access by engagement status and by link,
  acknowledgement for the CA, admin 403, links tick, general links, several filings, upload-and-link, key and
  filing checks, unlink, filed filings fixed, `with_ca` filings, delete rules); frontend `DocumentsPage.test.jsx`
  and the "filing page documents" tests in `FilingPage.test.jsx`.
- OCR runs in the upload request (a text PDF: milliseconds; a photo: well under a second on a laptop).
- **Tests:** `tests/test_ocr.py` (reading PDFs, photos and scans; the facts found; nothing personal stored; type
  warning; verified / not verified filings, typed ARN, unreadable file, undo, the CA path; auto-fill).

## Tables
Created by migration `schema: complete data model`; no migration in this module yet. Columns, constraints and status
values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/documents.py`.
- `documents`: file metadata, owned by a user (business user, or CA for the Certificate of Practice) and uploaded by
  a user (can differ); OCR status and fields; soft delete
- `compliance_item_documents`: which documents serve which filings (N–N, per checklist key or `general`); unlinking
  deletes the row

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| POST | `/api/v1/documents` (multipart: `file`, `doc_type`, `fy?`, `period_label?`, `compliance_item_id?`, `checklist_key?`) | business | 201 the document · 400 `FILE_EMPTY`, `FILE_TYPE_NOT_ALLOWED`, `FILE_TOO_LARGE` · 404 `BUSINESS_NOT_FOUND`, `FILING_NOT_FOUND` · 409 `FILING_LOCKED` · 422 `UNKNOWN_CHECKLIST_KEY`, bad fields |
| GET | `/api/v1/documents?fy=&doc_type=&compliance_item_id=&page=&page_size=` | business | `{items: [document], page, page_size, total}`, newest first |
| GET | `/api/v1/documents/{id}/file` | business (owner), CA (active engagement) | the file · 404 `DOCUMENT_NOT_FOUND` |
| DELETE | `/api/v1/documents/{id}` | business | 204 · 404 `DOCUMENT_NOT_FOUND` · 409 `DOCUMENT_IN_USE` |
| POST | `/api/v1/documents/{id}/links` `{compliance_item_id, checklist_key="general"}` | business | the document · 404 `DOCUMENT_NOT_FOUND`, `FILING_NOT_FOUND` · 409 `FILING_LOCKED` · 422 `UNKNOWN_CHECKLIST_KEY` |
| DELETE | `/api/v1/documents/links/{link_id}` | business | 204 · 404 `LINK_NOT_FOUND` · 409 `FILING_LOCKED` |

A document: `{id, doc_type, original_filename, mime_type, size_bytes, fy, period_label, ocr_status, created_at,
links: [{id, compliance_item_id, form_code, period_label, checklist_key}], acknowledgement_of:
[{compliance_item_id, form_code, period_label}]}`.

## Service functions other modules call
- `add_document(owner_id, uploaded_by_id, upload, doc_type) -> Document` (flushes, calls `on_document_uploaded`, no
  commit), `read_document(document_id) -> (Document, bytes)`, `remove_document(document_id)` (no commit). Used by
  marketplace (certificate), compliance (acknowledgement) and admin (download).
- `document_ids_for_filings(filing_ids) -> set`: live documents linked to those filings (used by marketplace's
  `ca_can_access_document`, MA14).
- `get_document_file(user, document_id) -> (Document, bytes)`: the access-checked download (owner or allowed CA).
  The CA workspace opens files with `/api/v1/documents/{id}/file`.
- `attach_document(business, user, document_id, item_id, key) -> Document` (link without commit; ca_workspace
  fulfils a request with it), `documents_by_filing(filings) -> {filing id: [file]}` (the CA's client workspace).
- `verify_acknowledgement(document, filing) -> dict` (DO8; used by compliance for the business and the CA),
  `type_warning(document)` (DO9).

## Depends on
core-infra (encrypted storage, OCR), compliance (`get_filings_by_ids`, `checklist_keys`, `tick_checklist_entry`,
`filings_by_acknowledgement`, `DONE_STATUSES`, `FORM_FOLDERS`), marketplace (`own_profile_id`,
`ca_can_access_document`), core-auth (`current_business()`). documents ↔ compliance and documents ↔ marketplace
import each other's service modules (`from app.services import ...`); that works because none of them uses the
other while it is being imported. Keep it that way.

## Contracts (don't change without telling the team)
- Files are encrypted at rest and never leave the server (rule 2); OCR is local only
- Every upload calls `on_document_uploaded(document, data)` once, after the row has an id and before the commit
- `ocr_fields` holds only non-personal facts (never text, PAN, GSTIN or names)
- A CA opens a document only through `ca_can_access_document`; admins never get contents from these routes
- A filed filing's links and acknowledgement cannot be removed or deleted (they are its proof)

## Known issues
- A CA sees a client's files in the CA workspace (`documents_by_filing`) and uploads only acknowledgements (CW5);
  a fulfilled document request links its file to the filing, so `ca_can_access_document` covers it.
- Deleting keeps the encrypted file on disk (soft delete); nothing cleans up old files.
- The vault shows at most 100 files in the filing page's "link one from your vault" list.
