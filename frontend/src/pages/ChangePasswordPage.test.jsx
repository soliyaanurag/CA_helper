import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { loadSession } from "@/lib/session";
import { fakeApi, loginAs, renderApp } from "@/test/utils";

const URL = "/api/v1/auth/change-password";

async function fillForm({ current = "Old-Password-1", password = "New-Password-7" } = {}) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Current password"), current);
  await user.type(screen.getByLabelText("New password"), password);
  await user.type(screen.getByLabelText("Confirm new password"), password);
  await user.click(screen.getByRole("button", { name: "Change password" }));
}

describe("change password page", () => {
  it.each(["business", "ca", "admin"])("is linked from the %s sidebar", async (role) => {
    loginAs(role);
    fakeApi({});
    renderApp(`/${role}`);

    expect(await screen.findByRole("link", { name: "Change password" })).toHaveAttribute(
      "href",
      `/${role}/change-password`,
    );
  });

  it("changes the password and empties the form", async () => {
    loginAs("ca");
    const fetchMock = fakeApi({ [`POST ${URL}`]: [204] });
    renderApp("/ca/change-password");

    await fillForm();

    expect(await screen.findByRole("status")).toHaveTextContent("Your password is changed.");
    expect(screen.getByLabelText("Current password")).toHaveValue("");
    const [, init] = fetchMock.mock.calls.find(([path]) => path === URL);
    expect(init.headers.Authorization).toBe("Bearer token-for-ca");
    expect(JSON.parse(init.body)).toEqual({
      current_password: "Old-Password-1",
      new_password: "New-Password-7",
    });
  });

  it("shows a wrong current password without logging out", async () => {
    loginAs("business");
    fakeApi({
      [`POST ${URL}`]: [
        400,
        { error: { code: "WRONG_PASSWORD", message: "Your current password is wrong." } },
      ],
    });
    renderApp("/business/change-password");

    await fillForm();

    expect(await screen.findByRole("alert")).toHaveTextContent("Your current password is wrong.");
    expect(screen.getByRole("heading", { name: "Change password" })).toBeInTheDocument();
    expect(loadSession()).not.toBeNull();
  });
});
