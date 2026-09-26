import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { loadSession } from "@/lib/session";
import { fakeApi, loginAs, renderApp } from "@/test/utils";

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
});
