# Simplification progress

Log of the run that follows `SIMPLIFICATION_PLAN.md`. Re-read both files before each step.

**Standing rule from Anurag (30 Sep 2026):** do not disrupt current functionality except where the plan
(section 4) or the prompt explicitly says so.

How to check after every step:
- backend tests, frontend tests, `npm run build`
- `python api_snapshot.py --compare` (repo root; after step 1 inside the backend container:
  `docker compose exec backend python ../api_snapshot.py --compare`). It uses its own database
  `ca_helper_snapshot` on the same server, so it never touches the dev data.

## Answered questions

### Q1 (step 0): which main to start from?
PRs #35 (legal update) and #34 (FAQ pages + assistant eval) were open. **Answer:** Anurag merged both first;
the tag and branch were made after that.

## Step 0: baseline (done)
- main at `5add203` (after merging #35 and #34). Tagged `before-simplify` and pushed the tag. Branch `simplify`.
- Old tooling on main: `make test` = **644 backend tests passed, 240 frontend tests passed (36 files)**;
  `npm run build` OK.
- `api_snapshot.py` written. It builds a fresh `ca_helper_snapshot` database (`db.create_all()`, like the tests),
  runs `seed-demo` through the Flask CLI, logs in as the demo business, CA and admin, then calls:
  every GET route without ids as each role and anonymously; the list endpoints with the filters the frontend sends;
  every GET route with ids, the ids taken from list responses (up to 40 each); a few 404 cases.
  It records status codes, content type and, per JSON path, the value types (string / number / bool / null /
  list / object, plus money = `"1250.00"`, date, datetime, uuid). It finds `db` via `app.extensions["sqlalchemy"]`
  and the seed via the `seed-demo` command, so it works unchanged through the refactor.
- Baseline `api_snapshot_baseline.json`: 184 endpoint entries, every GET route called. A second run: no differences.
- Known gaps of the snapshot (the tests cover these): the demo data has no regulatory changes and no assistant
  history, so those list shapes are empty lists; POST responses are not recorded (except login).

## Step 1: Docker Compose, delete tooling (done)

### Q2 (step 1): the npm packages behind the deleted config files
The plan deletes `eslint.config.js`, `.prettierrc.json`, `.prettierignore` and `components.json`, but does not name the
npm packages that only they use (`eslint`, `@eslint/js`, `eslint-config-prettier`, `eslint-plugin-react-hooks`,
`eslint-plugin-react-refresh`, `globals`, `prettier`, `prettier-plugin-tailwindcss`, `shadcn`) or the `lint`,
`format`, `format:check` npm scripts, which would fail without their configs.
**Answer:** remove the 8 lint/format packages and the `lint`, `format`, `format:check` scripts; keep `shadcn`
(`src/index.css` imports `shadcn/tailwind.css`).

Done:
- `docker-compose.yml` exactly as plan section 9 (db without a host port, Mailpit, backend, worker with profile,
  frontend). `main.py` listens on 0.0.0.0; Vite proxies `/api` to `API_URL` or `http://127.0.0.1:8000`.
- Deleted: Makefile, scripts/, environment.yml, .vscode/, .editorconfig, .gitattributes, ruff.toml,
  backend/requirements-dev.txt (pytest moved into requirements.txt, ruff dropped), frontend .prettierrc.json,
  .prettierignore, eslint.config.js, components.json, jsconfig.json, .npmrc. npm: the 8 lint/format packages and
  scripts removed (Q2).
- CI installs `backend/requirements.txt`; ruff, ESLint and Prettier steps removed (migrations and OpenAPI steps
  stay until steps 2 and 5).
- `.env.example`: DATABASE_URL points at the `db` container, POSTGRES_*/DB_HOST_PORT/TEST_DATABASE_URL/MAIL_SERVER
  removed (compose sets them), secret placeholders with how to generate them. `.gitignore`: conda link and
  .vscode exceptions removed.
- CLAUDE.md moved to docs/old-CLAUDE.md; new CLAUDE.md = plan section 8 word for word.
- Local machine: the old `make infra` containers (project `ca-helper`) were stopped; their volume
  `ca-helper_pgdata` is kept (not deleted). The new stack uses a new volume `ca_helper_pgdata`.
  In `.env`, the host of DATABASE_URL was changed from localhost to `db` (nothing else in .env was changed).

Checks (all inside the containers):
- `docker compose up -d`: db, mailpit, backend, frontend up; `flask db upgrade` + `flask seed-demo` OK;
  /api/health OK directly and through the Vite proxy.
- backend 644 passed; frontend 240 passed (36 files); `npm run build` OK.
- Snapshot compare: no differences.
- Tests changed: none.
