import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

function entry(fields) {
  return {
    id: fields.id,
    type: "engagement_update",
    title: "Your CA accepted your request",
    body: "Meera Shah accepted your request at their listed prices.",
    link: "/business/engagements",
    read_at: null,
    created_at: "2026-09-27T10:30:00+00:00",
    ...fields,
  };
}

const TRAY = {
  items: [
    entry({ id: "n1" }),
    entry({
      id: "n2",
      title: "GSTR-1 (Q2 2026-27) is due in 7 days",
      read_at: "2026-09-27T11:00:00Z",
    }),
  ],
  page: 1,
  page_size: 10,
  total: 2,
};

function open(role = "business", answers = {}) {
  loginAs(role);
  const fetchMock = fakeApi({
    "GET /api/v1/alerts/notifications/unread-count": [200, { unread: 1 }],
    "GET /api/v1/alerts/notifications?page_size=10": [200, TRAY],
    "POST /api/v1/alerts/notifications/n1/read": [200, { ...TRAY.items[0], read_at: "now" }],
    "POST /api/v1/alerts/notifications/read-all": [200, { unread: 0 }],
    ...answers,
  });
  renderApp(`/${role}/change-password`);
  return fetchMock;
}

function posted(fetchMock, path) {
  return fetchMock.mock.calls.some(([url, init]) => url === path && init?.method === "POST");
}

describe("notification bell", () => {
  it.each(["business", "ca", "admin"])("shows the unread count for %s users", async (role) => {
    open(role);

    expect(
      await screen.findByRole("button", { name: "Notifications, 1 unread" }),
    ).toBeInTheDocument();
  });

  it("opens the tray; clicking an entry marks it read and opens its page", async () => {
    const fetchMock = open();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Notifications, 1 unread" }));
    const tray = screen.getByRole("dialog", { name: "Notifications" });
    await user.click(await screen.findByText("Your CA accepted your request"));

    expect(tray).not.toBeInTheDocument();
    expect(posted(fetchMock, "/api/v1/alerts/notifications/n1/read")).toBe(true);
    expect(await screen.findByRole("heading", { name: "My engagements" })).toBeInTheDocument();
  });

  it("lists read and unread entries and marks everything read", async () => {
    const fetchMock = open();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Notifications, 1 unread" }));
    expect(await screen.findByText("GSTR-1 (Q2 2026-27) is due in 7 days")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Mark all read" }));

    await waitFor(() =>
      expect(posted(fetchMock, "/api/v1/alerts/notifications/read-all")).toBe(true),
    );
  });

  it("says when there is nothing yet", async () => {
    open("ca", {
      "GET /api/v1/alerts/notifications/unread-count": [200, { unread: 0 }],
      "GET /api/v1/alerts/notifications?page_size=10": [
        200,
        { items: [], page: 1, page_size: 10, total: 0 },
      ],
    });

    await userEvent.setup().click(await screen.findByRole("button", { name: "Notifications" }));

    expect(await screen.findByText("No notifications yet.")).toBeInTheDocument();
  });
});
