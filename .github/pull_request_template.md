## Summary

<!-- What does this PR do, and why? One short paragraph.
     If it touches shared code (app/__init__.py, models.py, utils.py, routes.jsx, api.js, components/), shared config
     (docker-compose.yml, CI) or another feature, or changes a contract,
     say so here in the first line. -->

## Tests run

<!-- Paste the relevant output or tick what you ran. -->

- [ ] `docker compose exec backend pytest`
- [ ] `docker compose exec frontend npm test` and `npm run build`
- [ ] Tried it by hand (`docker compose up`)

## Checklist

- [ ] Module doc updated in `docs/modules/<module>.md` ("What exists now", tables, endpoints, contracts, known issues)
- [ ] Migration added? If yes: one migration, message prefixed with the module name, created after pulling main
- [ ] New dependencies? If yes, list them below (Python: pinned in `backend/requirements.txt`; frontend: `package.json`)
- [ ] Frontend calls updated after route/schema changes
- [ ] Touches shared code, shared config or another module? Then the summary says so clearly
- [ ] No secrets or `.env` committed
- [ ] `docs/DATA_MODEL.md` / `docs/DECISIONS.md` updated if the data model or conventions changed

## New dependencies

<!-- package==version and why, or "none" -->

none
