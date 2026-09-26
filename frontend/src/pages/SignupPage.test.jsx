import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, renderApp, testUser } from "@/test/utils";

const SIGNUP_URL = "/api/v1/auth/signup";

async function fillForm({ role = "Business", password = "Sunrise-2026", confirm = password } = {}) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Full name"), "  Asha Rao ");
  await user.type(screen.getByLabelText("Email"), "asha@example.com");
  await user.click(screen.getByLabelText(role));
  await user.type(screen.getByLabelText("Password"), password);
  await user.type(screen.getByLabelText("Confirm password"), confirm);
  await user.click(screen.getByRole("button", { name: "Create account" }));
}

describe("signup page", () => {
  it("checks the fields before calling the API", async () => {
    const fetchMock = fakeApi({});
    renderApp("/signup");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Password"), "no-digits-here");
    await user.type(screen.getByLabelText("Confirm password"), "something-else");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Enter your name.")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("The passwords do not match.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("creates the account, then asks for the emailed code", async () => {
    const fetchMock = fakeApi({ [`POST ${SIGNUP_URL}`]: [201, testUser("ca")] });
    const router = renderApp("/signup");

    await fillForm({ role: "Chartered Accountant" });

    expect(await screen.findByRole("heading", { name: "Verify your email" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/verify-email");
    expect(screen.getByLabelText("Email")).toHaveValue("asha@example.com");
    const [, init] = fetchMock.mock.calls.find(([path]) => path === SIGNUP_URL);
    expect(JSON.parse(init.body)).toEqual({
      full_name: "Asha Rao",
      email: "asha@example.com",
      password: "Sunrise-2026",
      role: "ca",
    });
  });

  it("shows the API's message when the email already has an account", async () => {
    fakeApi({
      [`POST ${SIGNUP_URL}`]: [
        409,
        { error: { code: "EMAIL_TAKEN", message: "An account with this email already exists." } },
      ],
    });
    renderApp("/signup");

    await fillForm();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "An account with this email already exists.",
    );
  });
});
