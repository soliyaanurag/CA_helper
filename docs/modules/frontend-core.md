# frontend-core: app shell, routing, layouts, design system, API client

## Purpose
Everything in `frontend/src/core/`: the React app shell, route aggregation from `features/*/routes.tsx`, the four layouts (public, business, CA, admin), shadcn/ui components, the typed API client, and (still to come) auth context, route guards, notification tray and the floating assistant widget shell.

## What exists now
Code: `frontend/src/core/`, `frontend/src/main.tsx`, `frontend/src/index.css`, frontend root configs (`vite.config.ts`, `tsconfig*.json`, `eslint.config.js`, `.prettierrc.json`, `components.json`, `Dockerfile`, `nginx.conf`).
- **Works:** Vite + React + TypeScript app with Tailwind and shadcn/ui (`badge`, `button`, `card`); route aggregation picking up all 9 `features/*/routes.tsx`; four layouts (`PublicLayout`, and `BusinessLayout` / `CaLayout` / `AdminLayout` sharing `AppShell` with sidebar nav); landing page with an API health badge; area index pages and a 404 page; TanStack Query client; typed openapi-fetch client (`api`, `baseUrl: ""` because generated paths already include `/api/v1`) with `useHealth()`; enum code → display label maps (`core/labels.ts`: `COMPLIANCE_STATUS_LABELS`, `ENGAGEMENT_STATUS_LABELS`, `label()`); `ModulePlaceholder` used by every feature page. TypeScript `strict` is on in both tsconfigs. Node 22 and npm come from the conda env; every npm command runs through `conda run` (Makefile, pre-commit, `make setup`).
- **Tests:** `src/core/routes.test.tsx` (3 Vitest tests: every module's routes are collected, a module page renders in its layout with nav links, module admin screens register in the admin area); `src/core/labels.test.ts` (3 tests: known code, unknown-code fallback, snake_case codes).
- **Not built yet:** auth context and route guards (the layouts are open), notification tray, floating assistant widget, auth header on API calls.

## Tables
None (frontend).

## Endpoints
None (frontend). Calls `GET /api/health` on the landing page.

## Service functions other modules call
Frontend exports other features use:
- `api` from `@/core/api/client`: typed openapi-fetch client (`api.GET("/api/v1/...")`)
- `FeatureRoutes`, `NavItem`, `Area` types from `@/core/routing`
- `ModulePlaceholder` from `@/core/components/ModulePlaceholder`
- `label()` and the `*_LABELS` maps from `@/core/labels`: display text for enum codes (must match `docs/DATA_MODEL.md` "Status values")
- shadcn/ui components from `@/core/components/ui/*` (add more with `conda run -n ca-helper --cwd frontend npx shadcn@latest add <name>`)
- Planned: `useAuth()`, route guards

## Depends on
core-infra (OpenAPI spec via `make gen-api`), core-auth (auth context needs login/refresh endpoints).

## Contracts (don't change without telling the team)
- Each feature exports `routes: FeatureRoutes` from `features/<module>/routes.tsx`; paths are relative to the area prefix (`/app`, `/ca`, `/admin`); module admin screens live in `features/<module>/admin/` and register under `admin`
- API types are generated into `src/core/api/generated/` (gitignored); never hand-write API types
- Enum codes from the API are shown only through `label()` / the maps in `core/labels.ts`, never as raw codes

## Known issues
- Layouts are not guarded yet (no auth context).
- `npm run typecheck`, `lint`, `test` and `build` need `make gen-api` first (the Makefile targets do it for you).
