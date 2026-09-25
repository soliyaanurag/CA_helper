# Ownership

| Owner | Core pieces | Modules (owner builds backend + frontend + tests + seed data) | Form content |
|---|---|---|---|
| **Member A: Business domain** | `core/auth`, `core/permissions` | `onboarding`, `compliance`; admin editors for own config tables | ITR |
| **Member B: Infrastructure, documents & AI** | `core/db`, `core/security`, `core/email`, `core/notifications`, `core/ai`, `core/ocr`, `core/storage`, `core/errors.py`, `core/health.py`, `worker` | `alerts` (all scheduled user alerts + penalty estimator), `documents`, `assistant`, `regulatory` (incl. news-approval admin screen) | GSTR-1, GSTR-3B |
| **Member C: CA side & platform shell** | Frontend `core` (shell, routing, layouts, guards, design system, API client, auth context) | `marketplace`, `ca_workspace`, `admin` (shell, user/CA management, service catalog editor) | CMP-08, GSTR-4, 24Q, 26Q |

Root configs (Makefile, docker-compose, CI, environment.yml, requirements, ruff.toml, pre-commit) and `scripts/`
belong to Member B's core-infra; `docs/` shared files are edited by everyone in their own sections.

## Where each module lives

| Module | Backend | Frontend | Tracker |
|---|---|---|---|
| onboarding (A) | `backend/app/modules/onboarding/` | `frontend/src/features/onboarding/` | `docs/modules/onboarding.md` |
| compliance (A) | `backend/app/modules/compliance/` | `frontend/src/features/compliance/` | `docs/modules/compliance.md` |
| alerts (B) | `backend/app/modules/alerts/` | `frontend/src/features/alerts/` | `docs/modules/alerts.md` |
| documents (B) | `backend/app/modules/documents/` | `frontend/src/features/documents/` | `docs/modules/documents.md` |
| assistant (B) | `backend/app/modules/assistant/` | `frontend/src/features/assistant/` | `docs/modules/assistant.md` |
| regulatory (B) | `backend/app/modules/regulatory/` | `frontend/src/features/regulatory/` | `docs/modules/regulatory.md` |
| marketplace (C) | `backend/app/modules/marketplace/` | `frontend/src/features/marketplace/` | `docs/modules/marketplace.md` |
| ca_workspace (C) | `backend/app/modules/ca_workspace/` | `frontend/src/features/ca_workspace/` | `docs/modules/ca_workspace.md` |
| admin (C) | `backend/app/modules/admin/` | `frontend/src/features/admin/` | `docs/modules/admin.md` |
| core auth (A) | `backend/app/core/auth/`, `core/permissions.py` | (auth pages decided in AUTH-01) | `docs/modules/core-auth.md` |
| core infra (B) | `backend/app/core/*` (except auth, permissions), `backend/worker.py` | none | `docs/modules/core-infra.md` |
| frontend core (C) | none | `frontend/src/core/` | `docs/modules/frontend-core.md` |

## Rules
- Owners edit only their own module folders, their own `content/forms/<form>/` files, and their own lines in
  `docs/modules/*.md` (shared files `content.md` and `finish.md`: only your own task lines).
- **Admin screens are built by the owner of the data:**
  - Backend: under `/api/admin/<module>/...` in that module's blueprint.
  - Frontend: under `features/<module>/admin/`, registered into the admin layout by route aggregation
    (the `admin` key of `features/<module>/routes.tsx`).
- Changes to `core/`, root configs or another owner's files go in a **separate small PR** labelled `core` or
  `cross-module`, reviewed by the affected owner.
- Cross-module reads go through the other module's `services.py` functions, never by importing its models.
- **Exception:** during Phase 0 and Phase 1, the Builder creates code in everyone's folders. From Phase 2 on,
  ownership rules apply strictly.
