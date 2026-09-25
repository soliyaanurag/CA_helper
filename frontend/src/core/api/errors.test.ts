import { describe, expect, it } from "vitest";

import { ApiRequestError, errorMessage, unwrap } from "./errors";

function call(status: number, body: unknown) {
  const response = new Response(null, { status });
  return Promise.resolve(
    response.ok ? { data: body, response } : { error: body, response, data: undefined },
  );
}

describe("unwrap", () => {
  it("returns the data of a successful call", async () => {
    await expect(unwrap(call(200, { message: "hi" }))).resolves.toEqual({ message: "hi" });
  });

  it("throws ApiRequestError with the standard error body's fields", async () => {
    const body = { error: { code: "FORBIDDEN", message: "No access.", request_id: "req-9" } };

    const error = await unwrap(call(403, body)).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect(error).toMatchObject({ status: 403, code: "FORBIDDEN", requestId: "req-9" });
    expect(errorMessage(error)).toBe("No access. (reference: req-9)");
  });

  it("still throws ApiRequestError when the body is not the standard shape", async () => {
    const error = await unwrap(call(502, "Bad gateway")).catch((e: unknown) => e);

    expect(error).toMatchObject({ status: 502, code: "HTTP_ERROR" });
  });
});

describe("errorMessage", () => {
  it("explains network failures", () => {
    expect(errorMessage(new TypeError("Failed to fetch"))).toMatch(/Cannot reach the server/);
  });
});
