# content: legal values, form content, evaluation data (shared file)

## Purpose
Parallel-track preparation work during Phases 0–1: verifying legal values from official sources, writing per-form content in `content/forms/<form>/`, and building evaluation datasets in `eval/`.

## Owner
Shared. Each owner edits only their own task lines.

Folders: `content/forms/`, `docs/TODO_VERIFY.md`, `eval/`

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [ ] CNT-01 · P1 · A · Verify legal values from official sources → fill docs/TODO_VERIFY.md
- [ ] CNT-02 · P1 · A · ITR explanation, instructions, checklist
- [ ] CNT-03 · P1 · B · GSTR-1 explanation, instructions, checklist
- [ ] CNT-04 · P1 · B · GSTR-3B explanation, instructions, checklist
- [ ] CNT-05 · P1 · C · CMP-08 explanation, instructions, checklist
- [ ] CNT-06 · P1 · C · GSTR-4 explanation, instructions, checklist
- [ ] CNT-07 · P1 · C · 24Q and 26Q explanation, instructions, checklist
- [ ] CNT-08 · P1 · A · Label ~100 business descriptions with NIC codes (NIC evaluation set)
- [ ] CNT-09 · P1 · C · Collect/create ~30 sample documents for OCR evaluation (no real personal data)

## Tables owned
None directly. Verified values are loaded into config tables by onboarding/compliance/alerts.

## Endpoints exposed
None.

## Service functions others may call
_None yet._

## Depends on
Nothing.

## Contracts others rely on
- `content/forms/<FORM>/{explanation.md, instructions.md, checklist.yaml}`; form owner edits only their own folder
- No real personal data in `eval/` (synthetic or fully anonymised only)

## Known issues
_None yet._

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0: created this doc and its task list.
