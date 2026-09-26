import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeApi } from "@/test/utils";

import { ApiRequestError, apiFetch, errorMessage, setAuth } from "./client";

afterEach(() => setAuth(null, () => {}));

describe("apiFetch", () => {
  it("returns the parsed JSON of a successful call", async () => {
    fakeApi({ "GET /api/v1/x": [200, { message: "hi" }] });

    await expect(apiFetch("/api/v1/x")).resolves.toEqual({ message: "hi" });
  });

  it("sends the body as JSON and the token as a Bearer header", async () => {
    const fetchMock = fakeApi({ "POST /api/v1/x": [201, {}] });
    setAuth("my-token", () => {});

    await apiFetch("/api/v1/x", { method: "POST", body: { name: "A" } });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.body).toBe('{"name":"A"}');
    expect(init.headers).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer my-token",
    });
  });

  it("throws ApiRequestError with the standard error body's code and message", async () => {
    fakeApi({ "GET /api/v1/x": [403, { error: { code: "FORBIDDEN", message: "No access." } }] });

    const error = await apiFetch("/api/v1/x").catch((e) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect(error).toMatchObject({ status: 403, code: "FORBIDDEN", message: "No access." });
    expect(errorMessage(error)).toBe("No access.");
  });

  it("still throws ApiRequestError when the body is not the standard shape", async () => {
    fakeApi({ "GET /api/v1/x": [502, "Bad gateway"] });

    const error = await apiFetch("/api/v1/x").catch((e) => e);

    expect(error).toMatchObject({ status: 502, code: "HTTP_ERROR" });
  });

  it("logs out on a 401 to a request that carried a token", async () => {
    const logout = vi.fn();
    setAuth("expired-token", logout);
    fakeApi({ "GET /api/v1/x": [401, { error: { code: "TOKEN_EXPIRED", message: "Expired." } }] });

    await apiFetch("/api/v1/x").catch(() => {});

    expect(logout).toHaveBeenCalledOnce();
  });

  it("does not log out on a 401 without a token (e.g. a wrong password)", async () => {
    const logout = vi.fn();
    setAuth(null, logout);
    fakeApi({ "POST /api/v1/auth/login": [401, { error: { code: "INVALID_CREDENTIALS" } }] });

    await apiFetch("/api/v1/auth/login", { method: "POST", body: {} }).catch(() => {});

    expect(logout).not.toHaveBeenCalled();
  });
});

describe("errorMessage", () => {
  it("explains network failures", () => {
    expect(errorMessage(new TypeError("Failed to fetch"))).toMatch(/Cannot reach the server/);
  });
});
