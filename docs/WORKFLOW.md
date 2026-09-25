# Workflow: git, sessions and shared context

Everyone on the team runs their own Claude Code session on this repo. Tasks are assigned and split outside the
repo; this file says how context is shared and how every session starts, runs and ends. The short version is the
checklist in the root `CLAUDE.md`.

## How context is shared between Claude sessions
- **Root `CLAUDE.md`** is loaded automatically at the start of every session (kept ≤120 lines). It imports
  `docs/SCOPE.md` and points to the other docs by path.
- **Module docs** (`docs/modules/<module>.md`) are the living context for each module. They are read
  **explicitly** at session start (not as nested CLAUDE.md files, whose auto-loading is unreliable).
  Sections: Purpose · What exists now · Tables · Endpoints · Service functions other modules call · Depends on ·
  Contracts (don't change without telling the team) · Known issues.
- **The repo is the single source of truth.** Anything decided in chat that affects others lands in `docs/` in the
  same PR (usually `DECISIONS.md`, `DATA_MODEL.md`, `API_CONVENTIONS.md` or a module doc).

## Session start
1. `git status`. If there are uncommitted changes you didn't make in this task, **stop and ask**.
2. `git fetch origin`, then `git switch main && git pull --ff-only`.
3. Choose a branch:
   - New task: `git switch -c <name>/<module>-<short-task>`, e.g. `anurag/documents-ack-upload`.
   - Continuing: switch to the branch and `git rebase origin/main`.
   - If a conflict touches files you didn't change in this task, **stop and ask**.
4. Read `docs/modules/<module>.md` and `docs/PATTERNS.md`.
5. Summarize what changed on main that matters for this module: check `docs/`, `backend/migrations/`,
   `backend/app/core/`, `frontend/src/core/`, and any modules listed under "Depends on".
   (`git log --oneline -20 origin/main -- docs backend/migrations backend/app/core frontend/src/core`)
6. **Environment check:**
   - The conda env `ca-helper` exists (`conda env list`); otherwise tell the user to run `make setup`.
   - If `environment.yml` or `backend/requirements*.txt` changed, run `make env-update`.
     If `frontend/package*.json` changed, run `conda run -n ca-helper --cwd frontend npm ci`.
   - `make infra` is running.
   - `make migrate`, `make gen-api` and `make test` pass **before** changing anything.

## While working
- Keep changes scoped to the task. If a change touches `core/`, shared config (root configs, `scripts/`, CI) or
  another module, say so clearly in the PR.
- Follow `docs/PATTERNS.md`. Copy the closest existing example rather than inventing a new pattern.
- Small commits in Conventional Commit style: `feat(documents): extract ARN from acknowledgement`,
  `fix(compliance): ...`, `docs(alerts): ...`, `chore(core): ...`, `test(...)`. Stage specific files;
  never `git add -A` blindly.
- **Migrations:**
  - Pull main right before `make migration name="<module>: <message>"`.
  - One migration per PR, message prefixed with the module name.
  - Never edit a migration that's already on main.
  - If Alembic reports multiple heads: `conda run -n ca-helper --cwd backend flask --app app db merge heads -m "merge heads"`.
- After route or schema changes, run `make gen-api` and fix the type errors it reveals in the frontend.
- **New dependency:**
  - Python: pin it (`package==x.y.z`) in `backend/requirements.txt` (runtime) or `requirements-dev.txt` (dev only),
    then `make env-update`. Never `conda install` a Python library.
  - Frontend: `conda run -n ca-helper --cwd frontend npm install <pkg>` (exact version is saved automatically).
  - Mention it in the PR.
- Every new service or route gets tests. Every new table gets seed data.

## Session end / before a PR
- `make lint` and `make test` pass and the frontend builds (`conda run -n ca-helper --cwd frontend npm run build`). Never leave the branch red.
- Update the module doc so it stays true: "What exists now", tables, endpoints, service functions, contracts and
  known issues.
- If the data model or conventions changed, update `docs/DATA_MODEL.md` / `docs/DECISIONS.md`.
- Show a summary and **ask before `git push`**. Then draft the PR description from
  `.github/pull_request_template.md` (`gh pr create` if available).

## Pull requests
- One task (or a few tightly related ones) per PR; title in Conventional Commit style.
- CI must be green. A teammate reviews before merging.
- If the PR touches `core/`, shared config or another module, or changes a contract, say so at the top of the
  description so the whole team sees it.
- Squash-merge into `main`.

## Never
Commit to main directly · force-push main · rewrite a branch someone else uses · run `git reset --hard` or delete
branches without asking · commit secrets or generated files (`.env`, `openapi.json`,
`frontend/src/core/api/generated/`, uploads).
