import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, renderApp } from "@/test/utils";

const FORGOT_URL = "/api/v1/auth/forgot-password";
const RESET_URL = "/api/v1/auth/reset-password";
const FROM_FORGOT = { pathname: "/reset-password", state: { email: "owner@example.com" } };

async function fillReset({ code = "123456", password = "New-Password-7", confirm = password }) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Code"), code);
  await user.type(screen.getByLabelText("New password"), password);
  await user.type(screen.getByLabelText("Confirm new password"), confirm);
  await user.click(screen.getByRole("button", { name: "Reset password" }));
}

describe("forgot and reset password", () => {
  it("goes from login to a reset code to a new password", async () => {
    const fetchMock = fakeApi({ [`POST ${FORGOT_URL}`]: [204], [`POST ${RESET_URL}`]: [204] });
    const router = renderApp("/login");
    const user = userEvent.setup();

    await user.click(screen.getByRole("link", { name: "Forgot password?" }));
    await user.type(await screen.findByLabelText("Email"), "owner@example.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));

    expect(await screen.findByRole("heading", { name: "Reset your password" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveValue("owner@example.com");
    await fillReset({});

    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(await screen.findByRole("status")).toHaveTextContent("Your password is reset.");
    const [, init] = fetchMock.mock.calls.find(([path]) => path === RESET_URL);
    expect(JSON.parse(init.body)).toEqual({
      email: "owner@example.com",
      code: "123456",
      new_password: "New-Password-7",
    });
  });

  it("shows the API's message for a wrong code", async () => {
    fakeApi({
      [`POST ${RESET_URL}`]: [400, { error: { code: "OTP_INVALID", message: "Wrong code." } }],
    });
    renderApp(FROM_FORGOT);

    await fillReset({});

    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong code.");
  });

  it("checks the new password before calling the API", async () => {
    const fetchMock = fakeApi({});
    renderApp(FROM_FORGOT);

    await fillReset({ password: "Good-Password-1", confirm: "Other-Password-1" });

    expect(await screen.findByText("The passwords do not match.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("can send a new code", async () => {
    fakeApi({ [`POST ${FORGOT_URL}`]: [204] });
    renderApp(FROM_FORGOT);

    await userEvent.setup().click(screen.getByRole("button", { name: "Send a new code" }));

    expect(await screen.findByRole("status")).toHaveTextContent("we sent it a new code");
  });
});
