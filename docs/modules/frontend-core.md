# frontend-core: app shell, routing, layouts, design system, API client

## Purpose
Everything in `frontend/src/core/`: the React app shell, route aggregation from `features/*/routes.tsx`, the four layouts (public, business, CA, admin), shadcn/ui components, the typed API client, the auth context and route guards, and (still to come) the notification tray and the floating assistant widget shell.

## What exists now
Code: `frontend/src/core/`, `frontend/src/main.tsx`, `frontend/src/index.css`, frontend root configs (`vite.config.ts`, `tsconfig*.json`, `eslint.config.js`, `.prettierrc.json`, `components.json`).
- **Works:** Vite + React + TypeScript app with Tailwind and shadcn/ui (`badge`, `button`, `card`, `input`, `label`); one explicit route list in `core/routes.tsx` that imports each feature's `routes` array and lists it in its area (`/business`, `/ca`, `/admin`), together with each area's sidebar links (`BUSINESS_NAV`, `CA_NAV`, `ADMIN_NAV`); each area is `RequireRole` around `AppShell` (sidebar, the user's name, Log out); `PublicLayout` for the landing and login pages; landing page with a Log in button and an API health badge; `/login` page (`core/pages/LoginPage.tsx`: React Hook Form + Zod, a clear message per API error code, redirect by role or back to the page the guard came from); auth (`core/auth/`: `AuthProvider`, `useAuth()`, `RequireRole`, `ROLE_HOME`; session in memory + localStorage; one `api.use()` middleware, registered when `AuthProvider.tsx` loads, adds the Bearer header and logs out on a 401); 404 page; TanStack Query client; typed openapi-fetch client (`api`, `baseUrl` = the page origin with no path, because generated paths already include `/api/v1`; `fetch` looked up per call so tests can stub it) with `useHealth()` (the landing badge tells "API up, database unavailable" (503) apart from "unreachable"); `unwrap()` + `ApiRequestError` + `errorMessage()` (`core/api/errors.ts`), which every query and the login use so failures carry the API's `code` and `message`; enum code → display label maps (`core/labels.ts`: `USER_ROLE_LABELS`, `label()`); `ModulePlaceholder` used by every placeholder feature page. TypeScript `strict` is on in both tsconfigs. Node 22 and npm come from the conda env; every npm command runs through `conda run` (Makefile, `make setup`).
- **Tests:** `src/core/routes.test.tsx` (a feature page renders in its area with the sidebar links, a feature's index route is the area home, an admin screen renders in the admin area); `src/core/labels.test.ts` (known code, unknown-code fallback); `src/core/pages/LoginPage.test.tsx` (validation, error messages for 401/403/429, redirect by role for all three roles with the token sent, return to the guarded page); `src/core/auth/auth.test.tsx` (guard: not logged in → /login, wrong role → own home, logged in → away from /login; logout on 401 and with the button); `src/core/api/errors.test.ts` (unwrap success, standard error body, non-standard body, network message); `src/core/pages/HomePage.test.tsx` (health badge ok vs database down). Test helpers in `src/test/utils.tsx`: `fakeApi({"GET /api/v1/...": [status, body]})` stubs fetch, `loginAs(role)`, `renderApp(path)`.
- **Not built yet:** signup, refresh-token cookie, notification tray, floating assistant widget.

## Tables
None (frontend).

## Endpoints
None (frontend). Calls `GET /api/health` on the landing page and `POST /api/v1/auth/login` from the login page.

## Service functions other modules call
Frontend exports other features use:
- `api` from `@/core/api/client`: typed openapi-fetch client (`api.GET("/api/v1/...")`)
- `unwrap()`, `ApiRequestError`, `errorMessage()` from `@/core/api/errors`: wrap every call as `unwrap(api.GET(...))`; show failures with `errorMessage(error)`; switch on `error.code` where a page needs to
- `NavItem` type from `@/core/layout/AppShell`
- `ModulePlaceholder` from `@/core/components/ModulePlaceholder`
- `useAuth()` (`user`, `login`, `logout`) from `@/core/auth/auth-context`; `RequireRole`, `ROLE_HOME`, `User`/`Role` types from `@/core/auth/...`; test helpers from `@/test/utils`
- `label()` and the `*_LABELS` maps from `@/core/labels` (add a map when an enum reaches the UI): display text for enum codes (must match `docs/DATA_MODEL.md` "Status values")
- shadcn/ui components from `@/core/components/ui/*` (add more with `conda run -n ca-helper --cwd frontend npx shadcn@latest add <name>`)

## Depends on
core-infra (OpenAPI spec via `make gen-api`), core-auth (auth context needs login/refresh endpoints).

## Contracts (don't change without telling the team)
- Each feature exports a plain `routes: RouteObject[]` from `features/<module>/routes.tsx`, with paths relative to its area (`/business`, `/ca`, `/admin`); `core/routes.tsx` imports it explicitly into that area and lists its sidebar links; a module may give its area's home as an `index: true` route; module admin screens live in `features/<module>/admin/` and go into the admin area
- API types are generated into `src/core/api/generated/` (gitignored); never hand-write API types
- Enum codes from the API are shown only through `label()` / the maps in `core/labels.ts`, never as raw codes

## Known issues
- The session (access token) is in localStorage until the refresh-token cookie exists.
- `npm run typecheck`, `lint`, `test` and `build` need `make gen-api` first (the Makefile targets do it for you).
