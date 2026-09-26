import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { fakeApi, renderApp, testUser } from "@/test/utils";

const DASHBOARD_URL = {
  business: "/api/v1/compliance/dashboard",
  ca: "/api/v1/ca-workspace/dashboard",
  admin: "/api/v1/admin/dashboard",
};

async function submitLogin(email = "someone@demo.local", password = "secret") {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Email"), email);
  await user.type(screen.getByLabelText("Password"), password);
  await user.click(screen.getByRole("button", { name: "Log in" }));
}

function apiError(status, code) {
  return [status, { error: { code, message: code, request_id: "req-1" } }];
}

describe("login form", () => {
  it("validates the fields before calling the API", async () => {
    const fetchMock = fakeApi({});
    renderApp("/login");

    await userEvent.setup().click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    [401, "INVALID_CREDENTIALS", "Wrong email or password."],
    [403, "ACCOUNT_INACTIVE", "This account is inactive. Please contact support."],
    [429, "TOO_MANY_REQUESTS", "Too many login attempts. Wait a minute and try again."],
  ])("shows a clear message for %i %s", async (status, code, message) => {
    fakeApi({ "POST /api/v1/auth/login": apiError(status, code) });
    renderApp("/login");

    await submitLogin();

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByRole("heading", { name: "Log in" })).toBeInTheDocument();
  });

  it.each(["business", "ca", "admin"])("sends a %s user to their own dashboard", async (role) => {
    const user = testUser(role);
    const fetchMock = fakeApi({
      "POST /api/v1/auth/login": [200, { access_token: "new-token", user }],
      [`GET ${DASHBOARD_URL[role]}`]: [200, { message: `Welcome, ${user.full_name}` }],
    });
    const router = renderApp("/login");

    await submitLogin(user.email);

    expect(
      await screen.findByRole("heading", { name: `Welcome, ${user.full_name}` }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(`/${role}`);
    // The dashboard request carried the new token.
    const dashboardRequest = fetchMock.mock.calls
      .map(([request]) => request)
      .find((request) => request.url.endsWith(DASHBOARD_URL[role]));
    expect(dashboardRequest?.headers.get("Authorization")).toBe("Bearer new-token");
  });

  it("returns to the page the guard sent the user from", async () => {
    const user = testUser("business");
    fakeApi({ "POST /api/v1/auth/login": [200, { access_token: "t", user }] });
    const router = renderApp("/business/compliance");

    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    await submitLogin(user.email);

    await waitFor(() => expect(router.state.location.pathname).toBe("/business/compliance"));
  });
});
