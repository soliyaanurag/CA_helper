/**
 * apiFetch(): the one way the frontend calls the backend.
 *
 *   apiFetch("/api/v1/compliance/dashboard")
 *   apiFetch("/api/v1/auth/login", { method: "POST", body: { email, password } })
 *
 * - Every URL is the full path ("/api/v1/..."). The Vite dev server forwards /api
 *   to Flask, so requests go to the page's own origin. Request and response fields
 *   are listed in Swagger at /api/docs.
 * - Sends `body` as JSON and returns the parsed JSON response (null if there is none).
 * - Adds `Authorization: Bearer <token>` while someone is logged in.
 * - Throws ApiRequestError (status, code, message) for every error response.
 * - A 401 on a request that carried a token logs the user out (the token expired or
 *   the account was deactivated).
 *
 * Usage, in api/<module>.js:
 *   queryFn: () => apiFetch("/api/v1/<module>/<resource>"),
 */

/**
 * A failed API call, carrying the standard error body (docs/API_CONVENTIONS.md):
 * switch on `code` (e.g. "INVALID_CREDENTIALS") and show `message`.
 */
export class ApiRequestError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

// The logged-in user's token and how to log them out. AuthProvider
// (context/AuthProvider.jsx) sets both through setAuth() whenever the session changes.
let accessToken = null;
let logout = () => {};

export function setAuth(token, logoutFunction) {
  accessToken = token;
  logout = logoutFunction;
}

export async function apiFetch(path, { method = "GET", body } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const response = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  // No body (204) or not JSON (e.g. a proxy's HTML error page): null.
  const data = await response.json().catch(() => null);
  if (response.ok) return data;

  if (response.status === 401 && headers.Authorization) logout();
  const error = data?.error; // the standard error body: {error: {code, message}}
  throw new ApiRequestError(
    response.status,
    error?.code ?? "HTTP_ERROR",
    error?.message ?? `The server answered ${response.status}.`,
  );
}

/** Text to show for any error thrown by a query: the API's message, or a network hint. */
export function errorMessage(error) {
  if (error instanceof ApiRequestError) return error.message;
  return "Cannot reach the server. Check your connection and try again.";
}
