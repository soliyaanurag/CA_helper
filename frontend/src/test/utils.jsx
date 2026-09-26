// Shared helpers for tests that render the whole app (routes + auth + API client).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter } from "react-router";
import { RouterProvider } from "react-router/dom";
import { vi } from "vitest";

import { AuthProvider } from "@/context/AuthProvider";
import { saveSession } from "@/lib/session";
import { appRoutes } from "@/routes";

/**
 * Replace fetch with a fake backend. Returns the mock, so tests can inspect the
 * requests it received (e.g. their Authorization header).
 */
export function fakeApi(routes) {
  const fetchMock = vi.fn(async (request) => {
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

export function testUser(role) {
  return {
    id: "8c9e6679-7425-40de-944b-e07fc1f90ae7",
    email: `${role}@demo.local`,
    full_name: `Test ${role}`,
    role,
  };
}

/** Start the test already logged in (a stored session, as after a real login). */
export function loginAs(role) {
  const user = testUser(role);
  saveSession({ accessToken: `token-for-${role}`, user });
  return user;
}

/** Render the real app routes at `path`; returns the router to check where we ended up. */
export function renderApp(path) {
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
