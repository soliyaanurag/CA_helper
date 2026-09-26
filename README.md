# CA Helper ("ComplianceConnect")

A two-sided web platform that tells Indian MSMEs, gig workers and small businesses which tax filings apply to
them and when, guides them to file themselves, or connects them with a fairly priced (or pro-bono) Chartered
Accountant, and keeps verifiable proof of what was filed. MTech CSE lab project, IIT Bombay.

- Product scope: [docs/SCOPE.md](docs/SCOPE.md) · Team workflow: [CLAUDE.md](CLAUDE.md) ("Session checklist") ·
  Module context: [docs/modules/](docs/modules/)
- Stack: Flask 3 + flask-smorest + SQLAlchemy 2 + Postgres (backend), React + Vite + TypeScript +
  Tailwind/shadcn (frontend), APScheduler worker, Docker Compose for Postgres + Mailpit, GitHub Actions.

## Requirements

| | WSL2 (Windows) | macOS | Linux |
|---|---|---|---|
| OS | Ubuntu on WSL2. **Native Windows is not supported.** | Intel or Apple Silicon | any recent distro |
| Repo location | **inside Linux**, e.g. `~/projects/ca-helper` (never under `/mnt/c`) | anywhere | anywhere |
| Docker | Docker Desktop for Windows with **WSL integration** enabled for your distro | Docker Desktop for Mac | Docker Engine + Compose plugin |
| Node.js | nothing to install: Node 22 LTS comes from the conda env | same | same |
| conda | [Miniforge](https://conda-forge.org/download/) recommended (`make setup` prints the install command if conda is missing) | same | same |
| git, make | `sudo apt install git make` | `xcode-select --install` | package manager |

## First-time setup

```bash
git clone https://github.com/soliyaanurag/CA_helper.git ~/projects/ca-helper
cd ~/projects/ca-helper
make setup            # safe to re-run; asks before installing anything system-level
```

`make setup` (`scripts/setup_dev.sh`) checks that conda is installed (if not, it prints the Miniforge install
command and stops), creates or updates the `ca-helper` conda env (Python 3.12 + Tesseract + Node 22 + all pip
packages), installs npm packages with the env's Node, creates `.env` with random dev secrets and generates the API
types. Then start developing (next section).

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

Terminal 2, the frontend (http://localhost:5173, proxies `/api` to port 8000):

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

**After changing backend routes or schemas, regenerate the frontend API types** (the frontend imports them from
`frontend/src/core/api/generated/`, which is not committed):

```bash
make gen-api              # exports the OpenAPI spec from Flask, then runs `npm run gen:api`
```

Both files land in `frontend/src/core/api/generated/` (`openapi.json` and `schema.d.ts`). `npm run gen:api` alone
only converts an existing `openapi.json`; it does not export a new one, so use `make gen-api` (it needs no
activated env). `npm run dev` keeps working with stale types, but `npm run
typecheck`, `npm run build` and your editor will report errors until you regenerate.

`backend/main.py` is only for this manual mode. The Make targets and CI do not use it.

## Daily development (Make targets)

Postgres and Mailpit run in Docker. Flask, the worker and Vite run on your machine for fast reloads.
Use one terminal per long-running command. (`make` alone lists every target.)

```bash
make infra          # Postgres + Mailpit in Docker (waits until healthy)
make migrate        # apply database migrations
make seed           # demo users, one per role (logins in "Quick start (manual)")
make dev-backend    # Flask API with auto-reload  -> http://localhost:8000
make dev-worker     # background jobs (APScheduler), separate process
make dev-frontend   # Vite dev server             -> http://localhost:5173
```

| What | URL |
|---|---|
| App | http://localhost:5173 |
| API health | http://localhost:8000/api/health |
| API routes | http://localhost:8000/api/v1/... (see API docs) |
| API docs (Swagger UI) | http://localhost:8000/api/docs |
| Mailpit (caught emails) | http://localhost:8025 |

## Command reference

Every Make target runs Python and Node inside the conda env through `conda run`, so it works without
activating anything, and never uses a system Python or Node. (Scripts, CI and Claude Code always go through
these targets or `conda run`; an activated env is only for running things by hand, as in "Quick start (manual)".)

| Make target | What it does | Raw command |
|---|---|---|
| `make setup` | one-time / re-runnable setup | `bash scripts/setup_dev.sh` |
| `make env-update` | sync env after `environment.yml` / `requirements*.txt` change | `conda env update -n ca-helper -f environment.yml --prune` |
| `make infra` | start db + Mailpit | `docker compose up -d --wait db mailpit` |
| `make infra-down` | stop db + Mailpit | `docker compose stop db mailpit` |
| `make dev-backend` | Flask dev server | `conda run --no-capture-output -n ca-helper --cwd backend flask --app app run --debug --port 8000` |
| `make dev-worker` | worker | `conda run --no-capture-output -n ca-helper --cwd backend python worker.py` |
| `make dev-frontend` | Vite dev server | `conda run --no-capture-output -n ca-helper --cwd frontend npm run dev` |
| `make test` | all tests: pytest (needs `make infra`), then Vitest | `conda run --no-capture-output -n ca-helper --cwd backend pytest`, then `conda run --no-capture-output -n ca-helper --cwd frontend npm test` |
| `make lint` | ruff + ESLint + Prettier + tsc | `conda run -n ca-helper ruff check backend`, `conda run -n ca-helper ruff format --check backend`, `conda run -n ca-helper --cwd frontend npm run lint` (then `format:check`, `typecheck`) |
| `make format` | auto-fix formatting | `conda run -n ca-helper ruff check --fix backend`, `conda run -n ca-helper ruff format backend`, `conda run -n ca-helper --cwd frontend npm run format` |
| `make migrate` | apply migrations | `conda run --no-capture-output -n ca-helper --cwd backend flask --app app db upgrade` |
| `make migration name="onboarding: add businesses"` | new migration | `conda run --no-capture-output -n ca-helper --cwd backend flask --app app db migrate -m "onboarding: add businesses"` |
| `make seed` | dev seed data | `conda run --no-capture-output -n ca-helper --cwd backend flask --app app seed` |
| `make gen-api` | OpenAPI → TypeScript types | `conda run -n ca-helper --cwd backend flask --app app openapi write --format=json ../frontend/src/core/api/generated/openapi.json && conda run -n ca-helper --cwd frontend npm run gen:api` |

## VS Code

- Open the repo folder (on Windows: from WSL with `code .`, using the WSL extension).
- Install the recommended extensions when prompted (`.vscode/extensions.json`).
- The Python interpreter is preset to `.conda-env/bin/python`, a link to your `ca-helper` env that `make setup`
  creates. If VS Code does not pick it up: **Ctrl/Cmd+Shift+P → "Python: Select Interpreter" → choose
  `ca-helper`** (or "Enter interpreter path" → `<your conda>/envs/ca-helper/bin/python`; find it with
  `conda env list`).

## Troubleshooting

- **"The command 'docker' could not be found in this WSL 2 distro"** although Docker Desktop is running: enable
  Docker Desktop → Settings → Resources → WSL integration for your distro, then run `wsl --shutdown` in PowerShell
  and reopen Ubuntu (and VS Code).
- **`permission denied ... docker.sock`** right after installing Docker Desktop: open a new terminal. If that is
  not enough, run `wsl --shutdown` in PowerShell and reopen Ubuntu. Check Docker Desktop → Settings → Resources
  → WSL integration.
- **`node: command not found` in your terminal:** expected. Node lives in the conda env; use the Make targets or
  `conda run -n ca-helper --cwd frontend npm <command>`. If `npm ci` rejects the Node version (needs 22.22+),
  run `make env-update`.
- **Port already in use:** another Postgres on 5432 → set `DB_HOST_PORT` and the port in `DATABASE_URL` /
  `TEST_DATABASE_URL` in `.env`. On macOS, never use port 5000 (AirPlay Receiver); the backend uses 8000.
- **Frontend type errors about `./generated/schema`:** run `make gen-api` (the types are generated, not committed).
- **`conda: command not found` inside make:** open a new terminal after `conda init`, or run
  `make CONDA=/path/to/conda <target>`.
- **Slow file watching / weird errors on WSL2:** the repo is probably under `/mnt/c`. Clone it inside Linux.
- **`git commit` fails with "pre-commit not found"** (clones set up before pre-commit was removed): delete the old
  hook with `rm .git/hooks/pre-commit`.
