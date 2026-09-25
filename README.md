# CA Helper ("ComplianceConnect")

A two-sided web platform that tells Indian MSMEs, gig workers and small businesses which tax filings apply to
them and when, guides them to file themselves, or connects them with a fairly priced (or pro-bono) Chartered
Accountant, and keeps verifiable proof of what was filed. MTech CSE lab project, IIT Bombay.

- Product scope: [docs/SCOPE.md](docs/SCOPE.md) · Who owns what: [docs/OWNERSHIP.md](docs/OWNERSHIP.md) ·
  Phases: [docs/PHASES.md](docs/PHASES.md) · Workflow: [docs/WORKFLOW.md](docs/WORKFLOW.md)
- Stack: Flask 3 + flask-smorest + SQLAlchemy 2 + Postgres/pgvector (backend), React + Vite + TypeScript +
  Tailwind/shadcn (frontend), APScheduler worker, Docker Compose, GitHub Actions.

## Requirements

| | WSL2 (Windows) | macOS | Linux |
|---|---|---|---|
| OS | Ubuntu on WSL2. **Native Windows is not supported.** | Intel or Apple Silicon | any recent distro |
| Repo location | **inside Linux**, e.g. `~/projects/ca-helper` (never under `/mnt/c`) | anywhere | anywhere |
| Docker | Docker Desktop for Windows with **WSL integration** enabled for your distro | Docker Desktop for Mac | Docker Engine + Compose plugin |
| Node.js | 22 LTS (≥ 22.22) via [nvm](https://github.com/nvm-sh/nvm) | same, or `brew install node@22` | same |
| conda | Miniforge recommended; `make setup` offers to install it | same | same |
| git, make | `sudo apt install git make` | `xcode-select --install` | package manager |

## First-time setup

```bash
git clone https://github.com/soliyaanurag/CA_helper.git ~/projects/ca-helper
cd ~/projects/ca-helper
make setup            # safe to re-run; asks before installing anything system-level
```

`make setup` (`scripts/setup_dev.sh`) detects your OS, finds conda (or offers to install Miniforge), creates or
updates the `ca-helper` conda env (Python 3.12 + Tesseract + all pip packages), checks Docker/Node/git, installs
npm packages, creates `.env` with random dev secrets, installs the git pre-commit hooks, generates the API types
and prints a ✅/⚠️ checklist. If it installed Miniforge, restart your terminal and VS Code afterwards.

Then:

1. Put your own Gemini key in `.env` (`GEMINI_API_KEY=`, from https://aistudio.google.com/apikey). Needed from Phase 1.
2. Create your personal identity file for Claude Code (never committed). Root `CLAUDE.md` imports it:

   ```markdown
   <!-- ~/.claude/ca-helper-member.md -->
   # Who I am on the CA Helper team
   I am **Member B** (<your name>): Infrastructure, documents & AI.
   I own: core/db, core/security, core/email, core/notifications, core/ai, core/ocr, worker;
   modules alerts, documents, assistant, regulatory; form content GSTR-1, GSTR-3B.
   My branch prefix is `b/`. Tracker lines with owner `B` are mine.
   ```
3. Start developing (next section).

## Daily development: hybrid mode (default)

Postgres and Mailpit run in Docker. Flask, the worker and Vite run on your machine for fast reloads.
Use one terminal per long-running command.

```bash
make infra          # Postgres + Mailpit in Docker (waits until healthy)
make migrate        # apply database migrations
make dev-backend    # Flask API with auto-reload  -> http://localhost:8000
make dev-worker     # background jobs (APScheduler), separate process
make dev-frontend   # Vite dev server             -> http://localhost:5173
```

| What | URL |
|---|---|
| App (hybrid) | http://localhost:5173 |
| API health | http://localhost:8000/api/health |
| API docs (Swagger UI) | http://localhost:8000/api/docs |
| Mailpit (caught emails) | http://localhost:8025 |

## Full-Docker mode

All five services (`db`, `mailpit`, `backend`, `worker`, `frontend`) in containers, using the same `.env`.
Used for milestone checks, integration testing and deployment. CI builds and smoke-tests it on every PR.

```bash
make up      # generates API types, builds images, starts everything, waits until healthy
make logs    # follow logs
make down    # stop (database volume is kept)
```

Frontend: http://localhost:8080 (nginx, proxies `/api`) · API: http://localhost:8000/api/docs · Mailpit: http://localhost:8025

## Command reference

Every Python command runs inside the conda env through `conda run` (never an activated env or system Python).

| Make target | What it does | Raw command |
|---|---|---|
| `make setup` | one-time / re-runnable setup | `bash scripts/setup_dev.sh` |
| `make env-update` | sync env after `environment.yml` / `requirements*.txt` change | `conda env update -n ca-helper -f environment.yml --prune` |
| `make infra` | start db + Mailpit | `docker compose up -d --wait db mailpit` |
| `make infra-down` | stop db + Mailpit | `docker compose stop db mailpit` |
| `make dev-backend` | Flask dev server | `conda run --no-capture-output -n ca-helper --cwd backend flask --app app run --debug --port 8000` |
| `make dev-worker` | worker | `conda run --no-capture-output -n ca-helper --cwd backend python worker.py` |
| `make dev-frontend` | Vite dev server | `cd frontend && npm run dev` |
| `make up` | full-Docker mode | `make gen-api && docker compose up -d --build --wait` |
| `make down` | stop containers | `docker compose down` |
| `make logs` | follow logs | `docker compose logs -f --tail=100` |
| `make test` | all tests | the two below |
| `make test-backend` | pytest (needs `make infra`) | `conda run --no-capture-output -n ca-helper --cwd backend pytest` |
| `make test-frontend` | Vitest | `cd frontend && npm test` |
| `make lint` | ruff + ESLint + Prettier + tsc | `conda run -n ca-helper ruff check backend`, `conda run -n ca-helper ruff format --check backend`, `cd frontend && npm run lint && npm run format:check && npm run typecheck` |
| `make format` | auto-fix formatting | `conda run -n ca-helper ruff check --fix backend`, `conda run -n ca-helper ruff format backend`, `cd frontend && npm run format` |
| `make migrate` | apply migrations | `conda run --no-capture-output -n ca-helper --cwd backend flask --app app db upgrade` |
| `make migration name="onboarding: add businesses"` | new migration | `conda run --no-capture-output -n ca-helper --cwd backend flask --app app db migrate -m "onboarding: add businesses"` |
| `make seed` | dev seed data | `conda run --no-capture-output -n ca-helper --cwd backend flask --app app seed` |
| `make gen-api` | OpenAPI → TypeScript types | `conda run -n ca-helper --cwd backend flask --app app openapi write --format=json ../openapi.json && cd frontend && npm run gen:api` |

## VS Code

- Open the repo folder (on Windows: from WSL with `code .`, using the WSL extension).
- Install the recommended extensions when prompted (`.vscode/extensions.json`).
- The Python interpreter is preset to `.conda-env/bin/python`, a link to your `ca-helper` env that `make setup`
  creates. If VS Code does not pick it up: **Ctrl/Cmd+Shift+P → "Python: Select Interpreter" → choose
  `ca-helper`** (or "Enter interpreter path" → `<your conda>/envs/ca-helper/bin/python`; find it with
  `conda env list`).

## Troubleshooting

- **`permission denied ... docker.sock`** right after installing Docker Desktop: open a new terminal. If that is
  not enough, run `wsl --shutdown` in PowerShell and reopen Ubuntu. Check Docker Desktop → Settings → Resources
  → WSL integration.
- **nvm's install script fails with an SSL error** (some networks block `raw.githubusercontent.com`): install nvm
  with git instead:
  `git clone --depth 1 --branch v0.40.8 https://github.com/nvm-sh/nvm.git ~/.nvm`, then add the three lines from
  the nvm README to `~/.bashrc` (or `~/.zshrc`), open a new terminal, and run `nvm install 22`.
- **Port already in use:** another Postgres on 5432 → set `DB_HOST_PORT` and the port in `DATABASE_URL` /
  `TEST_DATABASE_URL` in `.env`. On macOS, never use port 5000 (AirPlay Receiver); the backend uses 8000.
- **Frontend type errors about `./generated/schema`:** run `make gen-api` (the types are generated, not committed).
- **`conda: command not found` inside make:** open a new terminal after `conda init`, or run
  `make CONDA=/path/to/conda <target>`.
- **Slow file watching / weird errors on WSL2:** the repo is probably under `/mnt/c`. Clone it inside Linux.
