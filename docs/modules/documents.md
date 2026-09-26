# documents: encrypted vault and filing-proof OCR

## Purpose
Encrypted upload/download of documents (acknowledgements, checklist documents), the vault organised by FY/period/type, filing-proof OCR (ARN/ack number, date, period → Filed–verified) and document-type verification.

## What exists now
Skeleton only; no features yet.
- Backend: no code yet (no blueprint, models, schemas or services). Create `routes/documents.py`, `schemas/documents.py`, `services/documents_service.py` (and `models/documents.py`) when the first feature lands, and add the blueprint to `BLUEPRINTS` (docs/PATTERNS.md).
- Frontend: one placeholder page, "Document vault" at `/business/documents` (business nav), `frontend/src/pages/business/DocumentsPage.jsx`, built from `Placeholder`; no API hooks yet.
- The encrypted storage and OCR helpers it needs (`app/utils/storage.py`, `app/utils/ocr.py`) do not exist yet, nor do their packages (pytesseract, PyMuPDF) or the Tesseract binary in the conda env.

## Tables
None yet. Planned:
- `documents`: owner business, uploader, FY, period, type, storage key, mime, size, sha256, OCR status/fields, soft delete

## Endpoints
None yet. Planned: `/api/v1/documents/...` (upload, list, download).

## Service functions other modules call
None yet. Planned: `save_document(...)`, `get_document(...)`, `verify_acknowledgement(document_id)` (used by compliance, ca_workspace).

## Depends on
core-infra (encrypted storage, OCR), compliance (items), core-auth (access checks).

## Contracts (don't change without telling the team)
- Files are encrypted at rest and never leave the server (rule 2); OCR is local only

## Known issues
None yet.
