# frontend-core: app shell, routing, layouts, design system, API client

## Purpose
The shared frontend code: the React app shell, the route table (`src/routes.jsx`), the layouts (public and the
sidebar `AppShell` for the business, CA and admin areas), shadcn/ui components, the API client, the auth
context and route guard, and (still to come) the notification tray and the floating assistant widget shell.

## What exists now
Code: `frontend/src/routes.jsx`, `main.jsx`, `index.css`, `api/client.js`, `api/health.js`, `components/`,
`context/`, `hooks/`, `lib/`, `pages/HomePage.jsx`, `pages/LoginPage.jsx`, `pages/NotFoundPage.jsx`, frontend root
configs (`vite.config.js`, `jsconfig.json`, `eslint.config.js`, `.prettierrc.json`, `components.json`,
`Dockerfile`, `nginx.conf`).
- **Folders:** `api/` (API client + one hook file per module), `pages/` (`business/`, `ca/`, `admin/`, one
  folder per role), `components/` (`ui/` from shadcn plus shared components), `context/` (`AuthProvider`),
  `hooks/` (`useAuth`), `lib/` (`session`, `labels`, `queryClient`, `utils`), `test/` (Vitest setup and helpers).
- **Works:** Vite + React app in plain JavaScript (`.js`/`.jsx`) with Tailwind and shadcn/ui (`badge`, `button`, `card`, `input`,
  `label`); one explicit route table in `routes.jsx`: the public area (`/`, `/login`) in `PublicLayout`, and the
  `/business`, `/ca`, `/admin` areas built by `roleArea(role, children)`, each wrapped in `RequireRole` and
  rendered in `AppShell` (sidebar with the role's `NAV` links, the user's name and a Log out button, title from
  `USER_ROLE_LABELS`); each area's home is its `index: true` dashboard page; landing page with a Log in button and
  an API health badge; `/login` page (`pages/LoginPage.jsx`: React Hook Form + Zod, a clear message per API error
  code, redirect by role or back to the page the guard came from); auth (`AuthProvider`, `useAuth()`,
  `RequireRole`, `ROLE_HOME`; token in localStorage for now; Bearer header and logout-on-401 via an `api.use()`
  middleware); 404 page; TanStack Query client (`lib/queryClient.js`); openapi-fetch client (`api`,
  `baseUrl` = the page origin with no path, because every URL already includes `/api/v1`; `fetch` looked up
  per call so tests can stub it) with `useHealth()` (the landing badge tells "API up, database unavailable" (503)
  apart from "unreachable"); `unwrap()` + `ApiRequestError` + `errorMessage()` (`api/client.js`), which every
  query and the login use so failures carry the API's `code`, `message` and `requestId`; enum code → display label
  maps (`lib/labels.js`: `COMPLIANCE_STATUS_LABELS`, `ENGAGEMENT_STATUS_LABELS`, `USER_ROLE_LABELS`, `label()`);
  `Placeholder` used by every page that is not built yet. `jsconfig.json` only tells the editor about the `@/` alias. Node 22 and
  npm come from the conda env; every npm command runs through `conda run` (Makefile, pre-commit, `make setup`).
- **Tests:** `src/routes.test.jsx` (every sidebar link is inside its role's area, a page renders in its layout
  with the sidebar links, the dashboard is the area home, admin screens are served in the admin area);
  `src/lib/labels.test.js` (known code, unknown-code fallback, snake_case codes); `src/pages/LoginPage.test.jsx`
  (validation, error messages for 401/403/429, redirect by role for all three roles with the token sent, return
  to the guarded page); `src/context/AuthProvider.test.jsx` (guard: not logged in → /login, wrong role → own
  home, logged in → away from /login; logout on 401 and with the button); `src/api/client.test.js` (unwrap
  success, standard error body, non-standard body, network message); `src/pages/HomePage.test.jsx` (health badge
  ok vs database down). Test helpers in `src/test/utils.jsx`: `fakeApi({"GET /api/v1/...": [status, body]})`
  stubs fetch, `loginAs(role)`, `renderApp(path)`.
- **Not built yet:** signup, refresh-token cookie, notification tray, floating assistant widget.

## Tables
None (frontend).

## Endpoints
None (frontend). Calls `GET /api/health` on the landing page and `POST /api/v1/auth/login` from the login page.

## Service functions other modules call
Frontend exports other features use:
- `api`, `unwrap()`, `ApiRequestError`, `errorMessage()` from `@/api/client`: wrap every call as
  `unwrap(api.GET(...))`; show failures with `errorMessage(error)`; switch on `error.code` where a page needs to
- `NAV` and `appRoutes` in `@/routes`: add every new page and sidebar link there
- `NavItem` type and `AppShell` from `@/components/AppShell`; `Placeholder` from `@/components/Placeholder`
- `useAuth()` (`user`, `login`, `logout`) from `@/hooks/useAuth`; `RequireRole` from `@/components/RequireRole`;
  `ROLE_HOME`, `User`/`Role` types from `@/lib/session`; test helpers from `@/test/utils`
- `label()` and the `*_LABELS` maps from `@/lib/labels`: display text for enum codes (must match
  `docs/DATA_MODEL.md` "Status values")
- shadcn/ui components from `@/components/ui/*` (add more with
  `conda run -n ca-helper --cwd frontend npx shadcn@latest add <name>`)

## Depends on
core-infra (API endpoints, Swagger at `/api/docs`), core-auth (auth context needs login/refresh endpoints).

## Contracts (don't change without telling the team)
- Every page is registered in `src/routes.jsx`; child paths are relative to the role's area (`/business`, `/ca`,
  `/admin`), sidebar links in `NAV` are absolute; each area's home is its `index: true` route; admin screens live in
  `pages/admin/`
- Plain JavaScript only (`.js`/`.jsx`); API fields use the backend's snake_case names (Swagger at `/api/docs`)
- Enum codes from the API are shown only through `label()` / the maps in `lib/labels.js`, never as raw codes

## Known issues
- The session (access token) is in localStorage until the refresh-token cookie exists.
- No type checking: a renamed backend field is only caught by tests or at runtime, so keep API calls in `api/<m>.js`.
