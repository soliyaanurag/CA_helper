/**
 * apiFetch(): the one way the frontend calls the backend.
 *
 *   apiFetch("/api/v1/compliance/dashboard")
 *   apiFetch("/api/v1/auth/login", { method: "POST", body: { email, password } })
 *
 * - Every URL is the full path ("/api/v1/..."). The Vite dev server forwards /api
 *   to Flask, so requests go to the page's own origin. Request and response fields
 *   are listed in Swagger at /api/docs.
 * - Sends `body` as JSON (a FormData body, for file uploads, as it is) and returns the
 *   parsed JSON response (null if there is none). apiDownload() gets a file instead.
 * - Adds `Authorization: Bearer <token>` while someone is logged in.
 * - Throws ApiRequestError (status, code, message) for every error response.
 * - A 401 on a request that carried a token logs the user out (the token expired or
 *   the account was deactivated).
 * - A request with no answer after REQUEST_TIMEOUT_MS fails with code TIMEOUT, so a
 *   hung server shows a clear message instead of a page that never finishes.
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

// How long a request may take before it fails with code TIMEOUT.
export const REQUEST_TIMEOUT_MS = 20_000;

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
  const isForm = body instanceof FormData; // a file upload: the browser sets the type
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response;
  let data;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined || isForm ? body : JSON.stringify(body),
      signal: controller.signal,
    });
    // No body (204) or not JSON (e.g. a proxy's HTML error page): null.
    data = await response.json().catch(() => null);
  } catch (error) {
    if (!controller.signal.aborted) throw error; // a network failure: see errorMessage()
  } finally {
    clearTimeout(timer);
  }
  if (controller.signal.aborted) {
    throw new ApiRequestError(
      0,
      "TIMEOUT",
      "The server did not answer within 20 seconds. Try again in a moment.",
    );
  }
  if (response.ok) return data;

  if (response.status === 401 && headers.Authorization) logout();
  const error = data?.error; // the standard error body: {error: {code, message}}
  throw new ApiRequestError(
    response.status,
    error?.code ?? "HTTP_ERROR",
    error?.message ?? `The server answered ${response.status}.`,
  );
}

/**
 * Downloads a file the API sends (e.g. an admin opening a CA's certificate) as a Blob.
 * Throws ApiRequestError like apiFetch() when the API answers with an error.
 */
export async function apiDownload(path) {
  const response = await fetch(path, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
  if (response.ok) return response.blob();
  const data = await response.json().catch(() => null);
  if (response.status === 401 && accessToken) logout();
  throw new ApiRequestError(
    response.status,
    data?.error?.code ?? "HTTP_ERROR",
    data?.error?.message ?? `The server answered ${response.status}.`,
  );
}

/** Text to show for any error thrown by a query: the API's message, or a network hint. */
export function errorMessage(error) {
  if (error instanceof ApiRequestError) return error.message;
  return "Cannot reach the server. Check your connection and try again.";
}
