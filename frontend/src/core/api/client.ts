import createClient from "openapi-fetch";

import type { components, paths } from "./generated/schema";

/**
 * Typed API client. URLs, parameters and response bodies are checked against
 * the backend's OpenAPI spec. The types in ./generated/ come from
 * `make gen-api` and are never written by hand (and never committed).
 *
 * Requests go to the same origin: the Vite dev server proxies /api to Flask.
 * The auth header and "log out on 401" are added by AuthProvider (core/auth)
 * through `api.use(...)`.
 *
 * baseUrl is the page's own origin, with no path, on purpose: module routes live
 * under /api/v1, and the generated `paths` already contain that full prefix
 * ("/api/v1/compliance/items"), so a baseUrl of "/api/v1" would double it. The
 * unversioned "/api/health" works too. (An absolute origin behaves like "" in the
 * browser, and also lets tests, which run in Node, build requests.)
 *
 * `fetch` is looked up on every call instead of once, so tests can replace it
 * with vi.stubGlobal("fetch", ...).
 *
 * Usage: const { data, error } = await api.GET("/api/v1/<module>/<resource>");
 */
export const api = createClient<paths>({
  baseUrl: globalThis.location?.origin ?? "",
  fetch: (request) => globalThis.fetch(request),
});

/** Standard error body returned by every endpoint (see docs/API_CONVENTIONS.md). */
export type ApiErrorBody = components["schemas"]["Error"];
