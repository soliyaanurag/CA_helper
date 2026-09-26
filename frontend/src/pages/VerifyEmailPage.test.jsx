import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, renderApp } from "@/test/utils";

const VERIFY_URL = "/api/v1/auth/verify-email";
const RESEND_URL = "/api/v1/auth/verify-email/resend";
// As the signup page arrives here: the email in the location state.
const FROM_SIGNUP = { pathname: "/verify-email", state: { email: "asha@example.com" } };

function sentBody(fetchMock, url) {
  const [, init] = fetchMock.mock.calls.find(([path]) => path === url);
  return JSON.parse(init.body);
}

describe("verify email page", () => {
  it("verifies the code, then shows the login page with a notice", async () => {
    const fetchMock = fakeApi({ [`POST ${VERIFY_URL}`]: [204] });
    const router = renderApp(FROM_SIGNUP);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Code"), "123456");
    await user.click(screen.getByRole("button", { name: "Verify email" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Your email is verified. You can log in now.",
    );
    expect(screen.getByLabelText("Email")).toHaveValue("asha@example.com");
    expect(sentBody(fetchMock, VERIFY_URL)).toEqual({ email: "asha@example.com", code: "123456" });
  });

  it("shows the API's message for a wrong code", async () => {
    fakeApi({
      [`POST ${VERIFY_URL}`]: [400, { error: { code: "OTP_INVALID", message: "Wrong code." } }],
    });
    renderApp(FROM_SIGNUP);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Code"), "000000");
    await user.click(screen.getByRole("button", { name: "Verify email" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong code.");
  });

  it("accepts only a 6-digit code", async () => {
    const fetchMock = fakeApi({});
    renderApp(FROM_SIGNUP);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Code"), "12ab");
    await user.click(screen.getByRole("button", { name: "Verify email" }));

    expect(await screen.findByText("Enter the 6-digit code from the email.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends a new code on request", async () => {
    const fetchMock = fakeApi({ [`POST ${RESEND_URL}`]: [204] });
    renderApp(FROM_SIGNUP);

    await userEvent.setup().click(screen.getByRole("button", { name: "Send a new code" }));

    expect(await screen.findByRole("status")).toHaveTextContent("we sent it a new code");
    expect(sentBody(fetchMock, RESEND_URL)).toEqual({ email: "asha@example.com" });
  });

  it("needs a valid email before sending a new code", async () => {
    const fetchMock = fakeApi({});
    renderApp("/verify-email");

    await userEvent.setup().click(screen.getByRole("button", { name: "Send a new code" }));

    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
