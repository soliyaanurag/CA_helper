import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const SETTINGS = {
  items: [
    { type: "deadline_reminder", email_enabled: true },
    { type: "overdue", email_enabled: true },
    { type: "document_request", email_enabled: true },
    { type: "regulatory_update", email_enabled: true },
  ],
  always_emailed: ["engagement_update", "account"],
};

// What PUT /alerts/settings answers after switching deadline reminders off.
const SAVED = {
  ...SETTINGS,
  items: [{ type: "deadline_reminder", email_enabled: false }, ...SETTINGS.items.slice(1)],
};

function open(role, path) {
  loginAs(role);
  const fetchMock = fakeApi({
    "GET /api/v1/alerts/settings": [200, SETTINGS],
    "PUT /api/v1/alerts/settings": [200, SAVED],
  });
  renderApp(path);
  return fetchMock;
}

describe("notification settings", () => {
  it("switches off deadline reminder emails", async () => {
    const fetchMock = open("business", "/business/alerts");
    const box = await screen.findByRole("checkbox", { name: /Deadline reminder/ });
    expect(box).toBeChecked();

    await userEvent.setup().click(box);

    await waitFor(() => expect(box).not.toBeChecked());
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(call[1].body)).toEqual({
      items: [{ type: "deadline_reminder", email_enabled: false }],
    });
  });

  it("says engagement and account emails are always sent, with no switch", async () => {
    open("business", "/business/alerts");

    expect(await screen.findByText("CA request update: always emailed")).toBeInTheDocument();
    expect(screen.getByText("Account: always emailed")).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(4);
  });

  it("is in the CA's sidebar too", async () => {
    open("ca", "/ca/alerts");

    expect(await screen.findByRole("checkbox", { name: /Overdue filing/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Notification settings" })).toHaveAttribute(
      "href",
      "/ca/alerts",
    );
  });
});
