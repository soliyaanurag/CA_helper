# CA Helper ("ComplianceConnect")

A two-sided web platform that tells Indian MSMEs, gig workers and small businesses which tax filings apply to
them and when, guides them to file themselves, or connects them with a fairly priced (or pro-bono) Chartered
Accountant, and keeps verifiable proof of what was filed. It never files returns itself: it tracks, guides,
connects and verifies. MTech CSE lab project, IIT Bombay.

- Product scope: [docs/SCOPE.md](docs/SCOPE.md) · Rules for code: [CLAUDE.md](CLAUDE.md)
- Stack: Flask 3 + SQLAlchemy 2 + Postgres with pgvector (backend, `backend/app/`), React + Vite + JavaScript +
  Tailwind (frontend, `frontend/src/`), an APScheduler worker, Mailpit for email, all in Docker Compose.

## Run it

You need Docker: Docker Desktop on macOS, or on Windows with WSL2 (enable WSL integration for your Ubuntu distro
and keep the repo **inside Linux**, e.g. `~/projects/ca-helper`, never under `/mnt/c`); Docker Engine with the
Compose plugin (2.17+) on Linux. Nothing else: Python, Node, Postgres and Tesseract run in containers.

```bash
cp .env.example .env        # then fill in the three secrets (each line says how to make it)
docker compose up           # first time: builds the images (a few minutes)
```

In a second terminal, the first time only:

```bash
docker compose exec backend flask --app app db upgrade   # create the tables
docker compose exec backend flask --app app seed         # rules, forms, NIC codes, demo users
docker compose exec backend flask --app app seed-demo    # optional: the demo data below
```

Then open:

| What | Where |
|---|---|
| The app | http://localhost:5173 |
| The API (JSON under `/api/v1`, health check at `/api/health`) | http://localhost:8000 |
| Mailpit: every email the app sends (signup and reset codes, reminders) | http://localhost:8025 |

Other commands:

```bash
docker compose --profile worker up                              # also the scheduled jobs (only ONE teammate)
docker compose exec backend pytest                              # backend tests (their own database)
docker compose exec frontend npm test                           # frontend tests
docker compose exec frontend npm run build                      # production build check
docker compose exec backend flask --app app assistant ingest    # AI assistant knowledge base (needs GEMINI_API_KEY)
docker compose exec backend flask --app app regulatory scan     # read the news sources now
docker compose exec backend flask --app app reset-db            # empty the database and seed it again
docker compose up --build                                       # after a change to requirements.txt or package.json
```

Without `GEMINI_API_KEY` everything still works: the NIC suggestions, the assistant and the news monitor use
their keyword fallbacks. The evaluation scripts for the report are in [eval/](eval/README.md).

## Demo script

`flask seed-demo` adds fictional demo data once (`backend/app/demo_seed.py`): 14 businesses, their filings for
this financial year, engagements of the demo CA in every status, documents, document requests, notifications,
ratings, a pro-bono request and a CA waiting for verification. Every name, PAN, GSTIN and file is made up. It
gives `business@demo.local` a business (Asha Traders) only if that account has none yet. To start again from
scratch: `flask --app app reset-db`, then `flask --app app seed-demo`.

Demo logins: `business@demo.local` (`DemoBusiness#2026`; the other demo businesses are `demo-biz-01@demo.local` to
`demo-biz-13@demo.local` with the same password), `ca@demo.local` (`DemoCA#2026`), `admin@demo.local`
(`DemoAdmin#2026`).

A 10-minute walk through every flow:

| Minutes | Log in as | Show |
|---|---|---|
| 0–1 | (new) `/signup` | Sign up as a business; the code arrives in Mailpit; register a business and read the "why" of each profile line |
| 1–3 | `business@demo.local` | Dashboard: next deadline, overdue count, penalty exposure, the CA's document request in "To do", the bell. Calendar → an overdue filing (late fees) → an upcoming GSTR-3B: "How similar businesses file it" (10 micro proprietorships), the checklist with linked files, "Your CA asked for documents" (answer it from the vault). Mark a filing as filed with an acknowledgement: it becomes "Filed–verified" |
| 3–4 | `business@demo.local` | Document vault: filters, open a file, try to delete an acknowledgement (refused). Find a CA (filters, prices), typical fees, My engagements (completed and rated, active), Regulatory updates, Notification settings |
| 4–7 | `ca@demo.local` | My clients: three clients by urgency with "Why flagged". Asha Traders: profile, files (Open), the fulfilled request, ask for a document, **Mark as filed** with an ARN. Deadline batches: one GSTR-3B due date for three clients. My engagements: a new request (accept), a quote waiting, declined / expired / cancelled ones. Pro-bono queue: take the freelancer's request |
| 7–8 | `demo-biz-04@demo.local` | My engagements: accept or reject the CA's quote |
| 8–10 | `admin@demo.local` | Dashboard: filings by status and the overdue rate. Users & CAs: review the pending CA (Tanvi Kulkarni), open the certificate, verify. Regulatory news: the sources and **Scan now**; the changes found (those Gemini read are sent to the affected users at once) |

The AI assistant (the round button at the bottom right, for businesses and CAs) answers from our own guides and
the official FAQs, with sources, once the knowledge base is ingested.

## Working in a team

One task per branch, never on `main`: `git switch -c <name>/<module>-<task>`, small commits
(`feat(documents): ...`, `fix(...)`), `git push`, open a pull request, a teammate reviews, CI must be green, then
**Squash and merge**. After a merge, everyone runs `git pull` on `main`, and `docker compose up --build` if
`requirements.txt` or `package.json` changed.

## Troubleshooting

- **`docker: command not found` in WSL, or the API cannot reach the database:** Docker Desktop is not running (or
  its WSL integration is off for your distro). Start it, then `docker compose up` again. Your data is kept in the
  `pgdata` volume.
- **Emails never reach your inbox:** by design. Every email is caught by Mailpit: http://localhost:8025.
- **`permission denied ... docker.sock`** right after installing Docker Desktop: open a new terminal. If that is
  not enough, run `wsl --shutdown` in PowerShell and reopen Ubuntu.
- **Port already in use (5173, 8000 or 8025):** stop the other program using it. On macOS, AirPlay Receiver uses
  port 5000, not ours.
- **Slow file watching or strange errors on WSL2:** the repo is probably under `/mnt/c`. Clone it inside Linux.
