import createClient from "openapi-fetch";

import type { components, paths } from "./generated/schema";

/**
 * Typed API client. URLs, parameters and response bodies are checked against
 * the backend's OpenAPI spec. The types in ./generated/ come from
 * `make gen-api` and are never written by hand (and never committed).
 *
 * Requests go to the same origin: in hybrid mode Vite proxies /api to Flask,
 * in Docker nginx does. Auth headers will be added via `api.use(...)` once auth exists.
 *
 * Usage: const { data, error } = await api.GET("/api/health");
 */
export const api = createClient<paths>({ baseUrl: "" });

/** Standard error body returned by every endpoint (see docs/API_CONVENTIONS.md). */
export type ApiErrorBody = components["schemas"]["Error"];
