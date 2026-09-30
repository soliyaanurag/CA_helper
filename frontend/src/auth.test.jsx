import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { loadSession } from "@/lib";
import { fakeApi, loginAs, renderApp, testUser } from "@/test/utils";

describe("route guards", () => {
  it("send a visitor who is not logged in to /login", async () => {
    fakeApi({});
    const router = renderApp("/admin");

    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
  });

  it("send a user with the wrong role to their own home", async () => {
    loginAs("ca");
    fakeApi({ "GET /api/v1/ca-workspace/dashboard": [200, { message: "Welcome, Test ca" }] });
    const router = renderApp("/business/compliance");

    expect(await screen.findByRole("heading", { name: "Welcome, Test ca" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/ca");
  });

  it("send a logged-in user away from /login to their home", async () => {
    loginAs("admin");
    fakeApi({ "GET /api/v1/admin/dashboard": [200, { message: "Welcome, Test admin" }] });
    const router = renderApp("/login");

    await waitFor(() => expect(router.state.location.pathname).toBe("/admin"));
  });

  it.each(["/business/compliance", "/ca/profile"])(
    "send an admin who opens %s to the admin home",
    async (path) => {
      loginAs("admin");
      fakeApi({ "GET /api/v1/admin/dashboard": [200, { message: "Welcome, Test admin" }] });
      const router = renderApp(path);

      expect(
        await screen.findByRole("heading", { name: "Welcome, Test admin" }),
      ).toBeInTheDocument();
      expect(router.state.location.pathname).toBe("/admin");
    },
  );
});

describe("session", () => {
  it("logs out when the API answers 401", async () => {
    loginAs("business");
    fakeApi({
      "GET /api/v1/compliance/dashboard": [
        401,
        { error: { code: "TOKEN_EXPIRED", message: "Your session has expired." } },
      ],
    });
    const router = renderApp("/business");

    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
    expect(loadSession()).toBeNull();
  });

  it("logs out with the Log out button", async () => {
    loginAs("business");
    fakeApi({ "GET /api/v1/compliance/dashboard": [200, { message: "Welcome, Test business" }] });
    const router = renderApp("/business");

    await userEvent.setup().click(await screen.findByRole("button", { name: "Log out" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(loadSession()).toBeNull();
  });

  it("sends the next login to the role's home, not back to the page logged out from", async () => {
    const admin = loginAs("admin");
    fakeApi({
      "GET /api/v1/admin/dashboard": [200, { message: "Welcome, Test admin" }],
      "POST /api/v1/auth/login": [200, { access_token: "new-token", user: admin }],
    });
    const router = renderApp("/admin/users");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Log out" }));
    await screen.findByRole("heading", { name: "Log in" });
    expect(router.state.location.state?.from).toBeUndefined();
    await user.type(screen.getByLabelText("Email"), admin.email);
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/admin"));
  });

  // The guard replaces the page in the same render, so its queries cannot refetch
  // with the old token. This keeps it that way.
  it("sends no request with the old token after logging out", async () => {
    loginAs("business");
    const fetchMock = fakeApi({
      "GET /api/v1/compliance/dashboard": [200, { message: "Welcome, Test business" }],
    });
    renderApp("/business");
    await screen.findByRole("heading", { name: "Welcome, Test business" });
    const callsBefore = fetchMock.mock.calls.length;

    await userEvent.setup().click(screen.getByRole("button", { name: "Log out" }));
    await screen.findByRole("heading", { name: "Log in" });

    const after = fetchMock.mock.calls.slice(callsBefore);
    expect(after.filter(([, init]) => init?.headers?.Authorization)).toEqual([]);
  });
});

describe("consent", () => {
  it("asks a user from before consent once, then shows the app", async () => {
    const user = testUser("business");
    const fetchMock = fakeApi({
      "POST /api/v1/auth/login": [200, { access_token: "t", user, terms_accepted: false }],
      "POST /api/v1/auth/accept-terms": [204],
      "GET /api/v1/compliance/dashboard": [200, { message: "Welcome, Test business" }],
    });
    renderApp("/login");
    const person = userEvent.setup();
    await person.type(screen.getByLabelText("Email"), user.email);
    await person.type(screen.getByLabelText("Password"), "secret");
    await person.click(screen.getByRole("button", { name: "Log in" }));

    await person.click(await screen.findByRole("button", { name: "I agree" }));

    expect(
      await screen.findByRole("heading", { name: "Welcome, Test business" }),
    ).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([path]) => path === "/api/v1/auth/accept-terms")).toBe(true);
    expect(loadSession().termsAccepted).toBe(true);
  });

  it("does not ask a user who already accepted", async () => {
    const user = testUser("business");
    fakeApi({
      "POST /api/v1/auth/login": [200, { access_token: "t", user, terms_accepted: true }],
      "GET /api/v1/compliance/dashboard": [200, { message: "Welcome, Test business" }],
    });
    renderApp("/login");
    const person = userEvent.setup();
    await person.type(screen.getByLabelText("Email"), user.email);
    await person.type(screen.getByLabelText("Password"), "secret");
    await person.click(screen.getByRole("button", { name: "Log in" }));

    expect(
      await screen.findByRole("heading", { name: "Welcome, Test business" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "I agree" })).not.toBeInTheDocument();
  });
});
