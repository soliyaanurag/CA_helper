## Summary

<!-- What does this PR do, and why? One short paragraph.
     If it touches shared code (see CLAUDE.md "Folder map"), shared config (root configs, scripts/, CI) or another module, or changes a contract,
     say so here in the first line. -->

## Tests run

<!-- Paste the relevant output or tick what you ran. -->

- [ ] `make lint`
- [ ] `make test`
- [ ] Frontend builds (`conda run -n ca-helper --cwd frontend npm run build`)
- [ ] Tried it by hand (`make dev-backend` + `make dev-frontend`)

## Checklist

- [ ] Module doc updated in `docs/modules/<module>.md` ("What exists now", tables, endpoints, contracts, known issues)
- [ ] Migration added? If yes: one migration, message prefixed with the module name, created after pulling main
- [ ] New dependencies? If yes, list them below (Python: pinned in `backend/requirements*.txt`; frontend: `package.json`)
- [ ] Frontend calls updated after route/schema changes
- [ ] Touches shared code, shared config or another module? Then the summary says so clearly
- [ ] No secrets, `.env`, `openapi.json` or uploaded files committed
- [ ] `docs/DATA_MODEL.md` / `docs/DECISIONS.md` updated if the data model or conventions changed

## New dependencies

<!-- package==version and why, or "none" -->

none
