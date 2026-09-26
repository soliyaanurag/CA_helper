import type { ApiErrorBody } from "./client";

/**
 * A failed API call, carrying the standard error body (docs/API_CONVENTIONS.md):
 * switch on `code` (e.g. "INVALID_CREDENTIALS") and show `message`.
 */
export class ApiRequestError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

function isErrorBody(body: unknown): body is ApiErrorBody {
  return typeof body === "object" && body !== null && "error" in body;
}

/**
 * The data of an openapi-fetch call, or throw ApiRequestError. Use it in every
 * query/mutation so errors look the same everywhere:
 *
 *   queryFn: () => unwrap(api.GET("/api/v1/<module>/<resource>")),
 */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await call;
  if (response.ok) return data as T; // (undefined for 204 No Content)
  if (isErrorBody(error)) {
    throw new ApiRequestError(response.status, error.error.code, error.error.message);
  }
  throw new ApiRequestError(
    response.status,
    "HTTP_ERROR",
    `The server answered ${response.status}.`,
  );
}

/** Text to show for any error thrown by a query: the API's message, or a network hint. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message;
  return "Cannot reach the server. Check your connection and try again.";
}
