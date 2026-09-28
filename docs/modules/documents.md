# documents: encrypted vault and filing-proof OCR

## Purpose
Encrypted upload/download of documents (acknowledgements, checklist documents), the vault organised by FY/period/type, filing-proof OCR (ARN/ack number, date, period → Filed–verified) and document-type verification.

## What exists now
Storing files works; the first (and only) user is the CA's Certificate of Practice. No vault, routes or OCR yet.
- **Encrypted storage** (core-infra): `app/utils/storage.py` `save_file(data, mime_type)` checks the type by the file's first bytes (PDF, JPG, PNG only) and the size (`MAX_UPLOAD_MB`), encrypts with Fernet and writes it to `UPLOAD_DIR` (default `backend/instance/uploads`, gitignored) under a random key; `open_file(key)`, `delete_file(key)`. Tests: `tests/test_storage.py`.
- **`services/documents_service.py`:** `add_document(owner_id, uploaded_by_id, upload, doc_type)` stores the file and adds the `documents` row (name, type, size, SHA-256; no commit); `read_document(document_id)` → (row, bytes), 404 `DOCUMENT_NOT_FOUND`; `remove_document(document_id)` soft-deletes (the encrypted file stays).
- No blueprint yet: marketplace uploads the certificate, admin downloads it (admins only).
- Frontend: one placeholder page, "Document vault" at `/business/documents` (business nav), `frontend/src/pages/business/DocumentsPage.jsx`, built from `Placeholder`; no API hooks yet.
- The OCR helper (`app/utils/ocr.py`) does not exist yet, nor its packages (pytesseract, PyMuPDF) or the Tesseract binary in the conda env.

## Tables
Created by migration `schema: complete data model` (no service, route or page uses them yet). Columns, constraints and status values: `docs/DATA_MODEL.md`. Model file: `backend/app/models/documents.py`.
- `documents`: file metadata, owned by a user (business user, or CA for the Certificate of Practice) and uploaded by a user (can differ); OCR status and fields; soft delete
- `compliance_item_documents`: which documents serve which filings (N–N, per checklist key or `general`); unlinking deletes the row

## Endpoints
None yet. Planned: `/api/v1/documents/...` (upload, list, download).

## Service functions other modules call
- `add_document(owner_id, uploaded_by_id, upload, doc_type) -> Document` (no commit), `read_document(document_id) -> (Document, bytes)`, `remove_document(document_id)` (no commit). Used by marketplace (certificate) and admin (download).
- `document_ids_for_filings(filing_ids) -> set`: live documents linked to those filings (used by marketplace's
  `ca_can_access_document`, MA14).
- Planned: `verify_acknowledgement(document_id)` (used by compliance, ca_workspace).

## Depends on
core-infra (encrypted storage, OCR), compliance (items), core-auth (access checks).

## Contracts (don't change without telling the team)
- Files are encrypted at rest and never leave the server (rule 2); OCR is local only

## Known issues
None yet.
