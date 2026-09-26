## Summary

<!-- What does this PR do, and why? One short paragraph.
     If it touches core/, shared config (root configs, scripts/, CI) or another module, or changes a contract,
     say so here in the first line. -->

## Tests run

<!-- Paste the relevant output or tick what you ran. -->

- [ ] `make lint`
- [ ] `make test`
- [ ] Frontend builds (`conda run -n ca-helper --cwd frontend npm run build`)
- [ ] Tried it by hand (`make dev-backend` + `make dev-frontend`, or `python main.py` + `npm run dev`)

## Checklist

- [ ] Module doc updated in `docs/modules/<module>.md` ("What exists now", tables, endpoints, contracts, known issues)
- [ ] Migration added? If yes: one migration, message prefixed with the module name, created after pulling main
- [ ] New dependencies? If yes, list them below (Python: pinned in `backend/requirements*.txt`; frontend: `package.json`)
- [ ] `make gen-api` run after route/schema changes
- [ ] Touches `core/`, shared config or another module? Then the summary says so clearly
- [ ] No secrets, `.env`, `openapi.json`, generated types or uploaded files committed
- [ ] `docs/DATA_MODEL.md` / `docs/DECISIONS.md` updated if the data model or conventions changed

## New dependencies

<!-- package==version and why, or "none" -->

none
