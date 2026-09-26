import createClient from "openapi-fetch";

/**
 * API client (openapi-fetch). Every URL is the full path, e.g. "/api/v1/auth/me";
 * request and response fields are listed in Swagger at /api/docs.
 *
 * Requests go to the same origin: in hybrid mode Vite proxies /api to Flask,
 * in Docker nginx does. The auth header and "log out on 401" are added by
 * AuthProvider (context/AuthProvider.jsx) through `api.use(...)`.
 *
 * baseUrl is the page's own origin, with no path, because every URL already
 * contains the full "/api/v1/..." prefix. (An absolute origin behaves like "" in
 * the browser, and also lets tests, which run in Node, build requests.)
 * `fetch` is looked up on every call, so tests can replace it with vi.stubGlobal.
 *
 * Usage, in api/<feature>.js:
 *   queryFn: () => unwrap(api.GET("/api/v1/<feature>/<resource>")),
 */
export const api = createClient({
  baseUrl: globalThis.location?.origin ?? "",
  fetch: (request) => globalThis.fetch(request),
});

/**
 * A failed API call, carrying the standard error body: switch on `code`
 * (e.g. "INVALID_CREDENTIALS"), show `message`, and quote `requestId` for
 * unexpected errors so the matching log lines can be found.
 */
export class ApiRequestError extends Error {
  constructor(status, code, message, requestId) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

/** Standard error body of every endpoint (docs/API_CONVENTIONS.md): {error: {code, message, request_id}}. */
function isErrorBody(body) {
  return typeof body === "object" && body !== null && "error" in body;
}

/** The data of an openapi-fetch call, or throw ApiRequestError. Use it in every query/mutation. */
export async function unwrap(call) {
  const { data, error, response } = await call;
  if (response.ok) return data; // (undefined for 204 No Content)
  if (isErrorBody(error)) {
    const { code, message, request_id } = error.error;
    throw new ApiRequestError(response.status, code, message, request_id);
  }
  throw new ApiRequestError(
    response.status,
    "HTTP_ERROR",
    `The server answered ${response.status}.`,
  );
}

/** Text to show for any error thrown by a query: API message (+ reference) or a network hint. */
export function errorMessage(error) {
  if (error instanceof ApiRequestError) {
    return error.requestId ? `${error.message} (reference: ${error.requestId})` : error.message;
  }
  return "Cannot reach the server. Check your connection and try again.";
}
