# CA Helper ("ComplianceConnect")

A two-sided web platform that tells Indian MSMEs, gig workers and small businesses which tax filings apply to
them and when, guides them to file themselves, or connects them with a fairly priced (or pro-bono) Chartered
Accountant, and keeps verifiable proof of what was filed. MTech CSE lab project, IIT Bombay.

- Product scope: [docs/SCOPE.md](docs/SCOPE.md) · How we work (git, sessions, rules): [CLAUDE.md](CLAUDE.md) ·
  Module context: [docs/modules/](docs/modules/)
- Stack: Flask 3 + flask-smorest + SQLAlchemy 2 + Postgres (backend), React + Vite + JavaScript +
  Tailwind/shadcn (frontend), APScheduler worker, Postgres and Mailpit in Docker, GitHub Actions.

## Requirements

| | WSL2 (Windows) | macOS | Linux |
|---|---|---|---|
| OS | Ubuntu on WSL2. **Native Windows is not supported.** | Intel or Apple Silicon | any recent distro |
| Repo location | **inside Linux**, e.g. `~/projects/ca-helper` (never under `/mnt/c`) | anywhere | anywhere |
| Docker (runs Postgres + Mailpit) | Docker Desktop for Windows with **WSL integration** enabled for your distro | Docker Desktop for Mac | Docker Engine + Compose plugin |
| Node.js | nothing to install: Node 22 LTS comes from the conda env | same | same |
| conda | [Miniforge](https://conda-forge.org/download/); `make setup` prints the install command if conda is missing | same | same |
| git, make | `sudo apt install git make` | `xcode-select --install` | package manager |

## First-time setup

```bash
git clone https://github.com/soliyaanurag/CA_helper.git ~/projects/ca-helper
cd ~/projects/ca-helper
make setup            # safe to re-run
```

`make setup` (`scripts/setup_dev.sh`) creates or updates the `ca-helper` conda env (Python 3.12 + Node 22 + all
pip packages), installs the npm packages with the env's Node, and creates `.env` with random secrets (an existing
`.env` is left alone). If conda is missing, it prints the Miniforge install command and stops.

Then start Docker Desktop and finish with:

```bash
make sync             # Postgres + Mailpit, migrations, seed data (and it records the installed packages)
make doctor           # should end with "Everything needed is in place."
gh auth login         # once, for make pr / make merge (GitHub CLI: sudo apt install gh, or brew install gh)
```

## Quick start (manual)

The simplest way to run the app by hand: two terminals with the conda env activated.

```bash
make infra                # Postgres + Mailpit in Docker
make migrate && make seed # first time, and after pulling new migrations/seed data
```

Terminal 1, the API (http://127.0.0.1:8000, Swagger at http://127.0.0.1:8000/api/docs):

```bash
conda activate ca-helper
cd backend
python main.py            # Flask dev server with debugger and auto-reload
```

Terminal 2, the frontend (http://localhost:5173, forwards `/api` to port 8000):

```bash
conda activate ca-helper
cd frontend
npm run dev
```

Log in at http://localhost:5173/login with a demo user from `.env` (`DEMO_*` variables, created by `make seed`):

| Role | Email | Password |
|---|---|---|
| Business | `business@demo.local` | `DemoBusiness#2026` |
| CA | `ca@demo.local` | `DemoCA#2026` |
| Admin | `admin@demo.local` | `DemoAdmin#2026` |

(These are the `.env.example` defaults; if your `.env` predates them, copy the `DEMO_*` block into it and run
`make seed`.)

To try signup, open http://localhost:5173/signup. The 6-digit verification code (and any password reset code)
arrives in Mailpit at http://localhost:8025; no email leaves your machine. Demo users are already verified.

## Daily development

Postgres and Mailpit run in Docker. Flask, the worker and Vite run on your machine for fast reloads.
Use one terminal per long-running command. The Make targets run the same commands as the manual quick start,
without activating the env yourself.

```bash
make infra          # Postgres + Mailpit in Docker (waits until healthy)
make migrate        # apply database migrations
make seed           # demo users, one per role (logins in "Quick start (manual)")
make dev-backend    # API (python main.py) with auto-reload -> http://localhost:8000
make dev-worker     # background jobs (APScheduler), separate process
make dev-frontend   # Vite dev server                      -> http://localhost:5173
```

| What | URL |
|---|---|
| App | http://localhost:5173 |
| API health | http://localhost:8000/api/health |
| API routes | http://localhost:8000/api/v1/... (see API docs) |
| API docs (Swagger UI) | http://localhost:8000/api/docs |
| Mailpit (caught emails) | http://localhost:8025 |

## Team workflow

**Every feature goes through these commands, for all three of us and for Claude Code.** They carry out the rules in
[CLAUDE.md](CLAUDE.md) ("Session checklist"), so a change reaches main tested, and works on everyone's machine
after they pull.

| When | Command | What it does |
|---|---|---|
| Something is off, or before you start | `make doctor` | checks git, the conda env, packages, `.env`, Docker, the database and the dev servers; changes nothing; every problem comes with its fix |
| Start a task | `make feature branch=anurag/documents-ack-upload` | pulls the latest main, runs `make sync`, then creates the branch `<name>/<module>-<short-task>` |
| Before pushing | `make check` | lint + format, migrations applied, exactly one migration head, no model change without a migration, all tests, frontend build |
| Send it for review | `make pr` | runs `make check`, pushes the branch, opens the pull request from the template (or updates the open one) |
| After a teammate approved | `make merge` | only when there are no conflicts, CI is green and nobody asked for changes: squash-merges, deletes the branch, then `make sync` on main |
| After someone else merged (or any time) | `make sync` | pulls main, reinstalls Python or npm packages only if their files changed, lists `.env` variables you lack, starts Postgres + Mailpit, migrates, seeds |

### One feature, start to finish

```bash
# You
make feature branch=anurag/documents-ack-upload   # latest main + a fresh branch
# ...build, commit in small Conventional Commits (feat(documents): ...)...
make pr                                            # checks, pushes, opens the pull request
#   On GitHub: fill in the template; a teammate reviews and approves; CI turns green.
make merge                                         # squash-merge into main, back on an up-to-date main

# Your teammates, after the merge
git switch main          # if they were on another branch (commit or stash their work first)
make sync                # same code, packages, tables and seed data as you
```

If `make sync` ends with "Packages changed", restart `make dev-backend`, `make dev-worker` and `make dev-frontend`.
Otherwise the running dev servers reload the new code by themselves.

**Continuing an existing branch** after main moved on: `git switch <branch>`, `git rebase origin/main` (on a
conflict: fix the files, `git add` them, `git rebase --continue`), then `make sync`. After a rebase of a branch
you already pushed, `make pr` asks you to run `git push --force-with-lease` once. That is safe on your own branch,
never on main.

### What the commands guarantee
- **Nothing is lost.** They refuse to switch branches with uncommitted changes, pull only fast-forward, never
  force-push, never touch main directly and never edit `.env`. `make doctor` changes nothing at all.
- **Nothing broken reaches main.** `make pr` pushes only after `make check` passes. `make merge` needs no conflicts,
  green CI and at least one approval (you cannot approve your own pull request), and it always squash-merges.
- **Every machine matches main after `make sync`.** New packages, migrations and seed data arrive with the pull;
  variables new in `.env.example` are listed so you can copy them.
- **Every failure says which step failed and what to do.** Examples:

| Message | What to do |
|---|---|
| `You have uncommitted changes` | commit them, or `git stash` them, then run the command again |
| `Docker is not running` | start Docker Desktop (WSL integration on), wait until it is running, run again |
| `main has new commits since you branched` | `git rebase origin/main`, then `make pr` again |
| `The database has a migration that this code does not know` | you are on an older branch: `git rebase origin/main` (on main: `git pull`), then `make sync` |
| `A model changed but no migration covers it` | `make migration name="<module>: <what changed>"`, review it, `make migrate`, commit |
| `Alembic has 2 migration heads` | run the `flask db merge heads` command it prints, commit the new file |
| `Your local main has N commit(s) that are not on GitHub` | follow the printed steps: keep them on a branch, reset main, `make pr` |
| `CI is still running` / `CI failed` | wait, or open the failed job on GitHub, fix, `make pr`, then `make merge` |
| `No teammate has approved yet` | ask a teammate to review the pull request on GitHub |
| `The GitHub CLI is not logged in` | `gh auth login` (only `make pr` and `make merge` need it) |

The commands live in `scripts/workflow.sh` (one function per command); the Makefile only calls it.

## Command reference

Every Make target runs Python and Node inside the conda env through `conda run`, so it works without
activating anything, and never uses a system Python or Node. (Scripts, CI and Claude Code always go through
these targets or `conda run`; an activated env is only for running things by hand, as in "Quick start (manual)".)
`make help` lists them all.

| Make target | What it does | Raw command |
|---|---|---|
| `make setup` | one-time / re-runnable setup | `bash scripts/setup_dev.sh` |
| `make env-update` | sync env after `environment.yml` / `requirements*.txt` change | `conda env update -n ca-helper -f environment.yml --prune` |
| `make infra` | start Postgres + Mailpit | `docker compose up -d --wait db mailpit` |
| `make infra-down` | stop Postgres + Mailpit | `docker compose stop db mailpit` |
| `make migrate` | apply migrations | `conda run --no-capture-output -n ca-helper --cwd backend flask --app app db upgrade` |
| `make migration name="onboarding: add businesses"` | new migration | `conda run --no-capture-output -n ca-helper --cwd backend flask --app app db migrate -m "onboarding: add businesses"` |
| `make seed` | dev seed data | `conda run --no-capture-output -n ca-helper --cwd backend flask --app app seed` |
| `make test` | all tests (backend needs `make infra`) | `conda run --no-capture-output -n ca-helper --cwd backend pytest`, then `conda run --no-capture-output -n ca-helper --cwd frontend npm test` |
| `make lint` | ruff + ESLint + Prettier | `conda run -n ca-helper ruff check backend`, `conda run -n ca-helper ruff format --check backend`, `conda run -n ca-helper --cwd frontend npm run lint` (then `format:check`) |
| `make format` | auto-fix formatting | `conda run -n ca-helper ruff check --fix backend`, `conda run -n ca-helper ruff format backend`, `conda run -n ca-helper --cwd frontend npm run format` |
| `make dev-backend` | Flask dev server | `conda run --no-capture-output -n ca-helper --cwd backend python main.py` |
| `make dev-worker` | worker | `conda run --no-capture-output -n ca-helper --cwd backend python worker.py` |
| `make dev-frontend` | Vite dev server | `conda run --no-capture-output -n ca-helper --cwd frontend npm run dev` |
| `make doctor` | check the whole setup, change nothing | `bash scripts/workflow.sh doctor` |
| `make feature branch=<name>/<module>-<task>` | latest main, sync, new branch | `bash scripts/workflow.sh feature <branch>` |
| `make sync` | match this machine to the checked-out code | `bash scripts/workflow.sh sync` |
| `make check` | everything before a push | `bash scripts/workflow.sh check` |
| `make pr` | check, push, open or update the pull request | `bash scripts/workflow.sh pr` |
| `make merge` | squash-merge an approved, green pull request | `bash scripts/workflow.sh merge` |

## VS Code

- Open the repo folder (on Windows: from WSL with `code .`, using the WSL extension).
- Install the recommended extensions when prompted (`.vscode/extensions.json`).
- The Python interpreter is preset to `.conda-env/bin/python`, a link to your `ca-helper` env that `make setup`
  creates. If VS Code does not pick it up: **Ctrl/Cmd+Shift+P → "Python: Select Interpreter" → choose
  `ca-helper`** (or "Enter interpreter path" → `<your conda>/envs/ca-helper/bin/python`; find it with
  `conda env list`).

## Troubleshooting

Run **`make doctor`** first: it checks the whole setup and prints a fix for each problem.

- **The API fails with `connection to server at "127.0.0.1", port 5432 failed: Connection refused`:** Postgres is
  down, almost always because Docker Desktop was closed. Start Docker Desktop, then `make infra`. Your data is kept.
- **`The command 'docker' could not be found in this WSL 2 distro`:** same cause: Docker Desktop is not running (or
  its WSL integration is off for your distro).
- **Emails (signup codes, reset codes) never reach your inbox:** by design in development. Every email is caught by
  Mailpit: open http://localhost:8025.
- **`permission denied ... docker.sock`** right after installing Docker Desktop: open a new terminal. If that is
  not enough, run `wsl --shutdown` in PowerShell and reopen Ubuntu. Check Docker Desktop → Settings → Resources
  → WSL integration.
- **`node: command not found` in your terminal:** expected. Node lives in the conda env; use the Make targets or
  `conda run -n ca-helper --cwd frontend npm <command>`. If npm says the Node version is too old (the frontend
  needs 22.22+), run `make env-update`.
- **Port already in use:** another Postgres on 5432 → set `DB_HOST_PORT` and the port in `DATABASE_URL` /
  `TEST_DATABASE_URL` in `.env`. On macOS, never use port 5000 (AirPlay Receiver); the backend uses 8000.
- **`conda: command not found` inside make:** open a new terminal after `conda init`, or run
  `make CONDA=/path/to/conda <target>`.
- **Slow file watching / weird errors on WSL2:** the repo is probably under `/mnt/c`. Clone it inside Linux.
