# frontend-core: app shell, routing, layouts, design system, API client

## Purpose
Everything in `frontend/src/core/`: the React app shell, route aggregation from `features/*/routes.tsx`, the four layouts (public, business, CA, admin), shadcn/ui components, the typed API client, and (Phase 1) auth context, route guards, notification tray and the floating assistant widget shell.

## Owner
Member C (CA side & platform shell)

Folders: `frontend/src/core/`, `frontend/src/main.tsx`, `frontend/src/index.css`, frontend root configs (`vite.config.ts`, `tsconfig*.json`, `eslint.config.js`, `.prettierrc.json`, `components.json`, `Dockerfile`, `nginx.conf`)

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [x] FE-01 · P0 · C · Vite + React + TS, Tailwind + shadcn/ui, route aggregation, role layouts, API client + gen:api
- [ ] FE-02 · P1 · C · Auth context, route guards, role-based navigation
- [ ] FE-03 · P1 · C · Notification tray UI + floating assistant widget shell
- [ ] FE-04 · P2 · C · Consistent loading/empty/error states, responsive layout polish

## Tables owned
None (frontend).

## Endpoints exposed
None (frontend). Calls `GET /api/health` on the landing page.

## Service functions others may call
Frontend exports other features use:
- `api` from `@/core/api/client`: typed openapi-fetch client (`api.GET("/api/...")`)
- `FeatureRoutes`, `NavItem`, `Area` types from `@/core/routing`
- `ModulePlaceholder` from `@/core/components/ModulePlaceholder`
- shadcn/ui components from `@/core/components/ui/*` (add more with `npx shadcn@latest add <name>` inside `frontend/`)
- Planned (FE-02): `useAuth()`, route guards

## Depends on
core-infra (OpenAPI spec via `make gen-api`), core-auth (FE-02 needs login/refresh endpoints).

## Contracts others rely on
- Each feature exports `routes: FeatureRoutes` from `features/<module>/routes.tsx`; paths are relative to the area prefix (`/app`, `/ca`, `/admin`); module admin screens live in `features/<module>/admin/` and register under `admin`
- API types are generated into `src/core/api/generated/` (gitignored); never hand-write API types

## Known issues
- Layouts are not guarded yet (FE-02).
- `npm run typecheck`, `lint`, `test` and `build` need `make gen-api` first (the Makefile targets do it for you).

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0 bootstrap: Vite + React + TS app, Tailwind + shadcn/ui, route aggregation, four layouts, placeholder page per module, typed API client + gen:api, first Vitest tests.
