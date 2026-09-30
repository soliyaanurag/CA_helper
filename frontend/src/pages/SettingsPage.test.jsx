import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

function open(role, path) {
  loginAs(role);
  const fetchMock = fakeApi({
    "GET /api/v1/auth/settings": [200, { email_notifications: true }],
    "PUT /api/v1/auth/settings": [200, { email_notifications: false }],
  });
  renderApp(path);
  return fetchMock;
}

describe("notification settings", () => {
  it("switches off the notification emails", async () => {
    const fetchMock = open("business", "/business/settings");
    const box = await screen.findByRole("checkbox", { name: /Email me my notifications/ });
    expect(box).toBeChecked();

    await userEvent.setup().click(box);

    await waitFor(() => expect(box).not.toBeChecked());
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(call[1].body)).toEqual({ email_notifications: false });
  });

  it("says login and password codes are always emailed, with one switch", async () => {
    open("business", "/business/settings");

    expect(
      await screen.findByText(/Login and password codes are always emailed/),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(1);
  });

  it("is in the CA's sidebar too", async () => {
    open("ca", "/ca/settings");

    expect(
      await screen.findByRole("checkbox", { name: /Email me my notifications/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Notification settings" })).toHaveAttribute(
      "href",
      "/ca/settings",
    );
  });
});
