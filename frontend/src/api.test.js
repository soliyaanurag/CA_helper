import { afterEach, describe, expect, it, vi } from "vitest";

import {
  apiDownload,
  apiFetch,
  ApiRequestError,
  errorMessage,
  REQUEST_TIMEOUT_MS,
  setAuth,
} from "@/api";
import { fakeApi } from "@/test/utils";

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
  it("fails with a clear TIMEOUT error when the server does not answer", async () => {
    vi.useFakeTimers();
    // A fetch that only ends when it is aborted, like a hung server.
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (path, init) =>
          new Promise((resolve, reject) =>
            init.signal.addEventListener("abort", () => reject(new DOMException("", "AbortError"))),
          ),
      ),
    );

    const call = apiFetch("/api/v1/x");
    const failed = expect(call).rejects.toMatchObject({ code: "TIMEOUT", status: 0 });
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS);
    await failed;
    vi.useRealTimers();
  });

  it("explains network failures", () => {
    expect(errorMessage(new TypeError("Failed to fetch"))).toMatch(/Cannot reach the server/);
  });
});

describe("file uploads and downloads", () => {
  it("sends a FormData body as it is, without a JSON content type", async () => {
    const fetchMock = fakeApi({ "POST /api/v1/x": [200, {}] });
    const form = new FormData();
    form.append("file", new Blob(["%PDF-"]), "cop.pdf");

    await apiFetch("/api/v1/x", { method: "POST", body: form });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.body).toBe(form);
    expect(init.headers["Content-Type"]).toBeUndefined();
  });

  it("downloads a file with the token, and throws the API's error", async () => {
    setAuth("my-token", () => {});
    const fetchMock = vi.fn(async (path) =>
      path === "/ok"
        ? new Response("file bytes", { status: 200 })
        : new Response(
            JSON.stringify({ error: { code: "CERTIFICATE_MISSING", message: "No file." } }),
            {
              status: 404,
            },
          ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const blob = await apiDownload("/ok");

    expect(await blob.text()).toBe("file bytes");
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer my-token");
    await expect(apiDownload("/missing")).rejects.toMatchObject({ code: "CERTIFICATE_MISSING" });
  });
});
