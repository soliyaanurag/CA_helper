// Shared helpers for tests that render the whole app (routes + auth + API client).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter } from "react-router";
import { RouterProvider } from "react-router/dom";
import { vi } from "vitest";

import { AuthProvider } from "@/core/auth/AuthProvider";
import { type Role, saveSession, type User } from "@/core/auth/session";
import { appRoutes } from "@/core/routes";

/** "METHOD /path" -> [status, JSON body]. Anything else returns 404. */
export type FakeApi = Record<string, [number, unknown]>;

/**
 * Replace fetch with a fake backend. Returns the mock, so tests can inspect the
 * requests it received (e.g. their Authorization header).
 */
export function fakeApi(routes: FakeApi) {
  const fetchMock = vi.fn(async (request: Request) => {
    const key = `${request.method} ${new URL(request.url).pathname}`;
    const [status, body] = routes[key] ?? [404, { error: { code: "NOT_FOUND", message: key } }];
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function testUser(role: Role): User {
  return {
    id: "8c9e6679-7425-40de-944b-e07fc1f90ae7",
    email: `${role}@demo.local`,
    full_name: `Test ${role}`,
    role,
  };
}

/** Start the test already logged in (a stored session, as after a real login). */
export function loginAs(role: Role): User {
  const user = testUser(role);
  saveSession({ accessToken: `token-for-${role}`, user });
  return user;
}

/** Render the real app routes at `path`; returns the router to check where we ended up. */
export function renderApp(path: string) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return router;
}
