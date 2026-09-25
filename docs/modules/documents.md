# documents: encrypted vault and filing-proof OCR

## Purpose
Encrypted upload/download of documents (acknowledgements, checklist documents), the vault organised by FY/period/type, filing-proof OCR (ARN/ack number, date, period → Filed–verified) and document-type verification.

## Owner
Member B (Infrastructure, documents & AI)

Folders: `backend/app/modules/documents/`, `frontend/src/features/documents/`

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [ ] DOC-01 · P1 · B · Encrypted upload/download of acknowledgement when marking filed
- [ ] DOC-02 · P2 · B · Document vault (upload per item, browse by FY/period/type, download)
- [ ] DOC-03 · P2 · B · Filing-proof OCR: extract ARN/ack number, date, period → Filed–verified
- [ ] DOC-04 · P3 · B · OCR document-type verification against the checklist
- [ ] DOC-05 · P5 · B · OCR field-accuracy evaluation on ~30 sample documents

## Tables owned
- `documents` (planned): owner business, uploader, FY, period, type, storage key, mime, size, sha256, OCR status/fields, soft delete

## Endpoints exposed
Planned: `/api/documents/...` (upload, list, download).

## Service functions others may call
- Planned: `save_document(...)`, `get_document(...)`, `verify_acknowledgement(document_id)` (used by compliance, ca_workspace)

## Depends on
core-infra (encrypted storage, OCR), compliance (items), core-auth (access checks).

## Contracts others rely on
- Files are encrypted at rest and never leave the server (rule 2); OCR is local only

## Known issues
_None yet._

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0: created this doc and its task list.
