# <module>: <one-line summary>

<!-- Copy this file to docs/modules/<module>.md for a new module.
     Files starting with "_" are ignored by scripts/progress.py. -->

## Purpose
What this module does for users, in 2-4 sentences.

## Owner
Member X (<area>)

Folders: `backend/app/modules/<module>/`, `frontend/src/features/<module>/`

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.
Use the middle dot `·` with a space on each side, exactly as below.

    - [ ] ABC-01 · P1 · A · Example task description

## Tables owned
- `table_name`: what one row means (link to docs/DATA_MODEL.md)

## Endpoints exposed
- `GET /api/<module>/...`: what it returns

## Service functions others may call
- `function_name(args) -> result`: what it guarantees

## Depends on
Other modules/core pieces this module calls.

## Contracts others rely on
Status values, codes, response shapes or behaviour other modules depend on. Change them only with a
`cross-module` PR reviewed by the affected owners.

## Known issues
- ...

## Session log
Newest first. Keep the last 10 entries.

- YYYY-MM-DD · Member X · what was done, what is next
