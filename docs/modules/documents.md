# documents: encrypted vault and filing-proof OCR

## Purpose
Encrypted upload/download of documents (acknowledgements, checklist documents), the vault organised by FY/period/type, filing-proof OCR (ARN/ack number, date, period → Filed–verified) and document-type verification.

## What exists now
Skeleton only; no features yet.
- Backend (`backend/app/modules/documents/`): only `__init__.py` and `routes.py`, whose `documents` blueprint is registered under `/api/v1` with no routes yet; no models, services or seed data; no tests yet.
- Frontend (`frontend/src/features/documents/`): one placeholder page, "Document vault" at `/business/documents` (business nav), built from `ModulePlaceholder`; no API hooks yet.
- The encrypted storage and OCR helpers it needs (`core/storage/`, `core/ocr/`) are planned in core-infra and do not exist yet.

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
