import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const CA_ID = "0b5f0b8e-4a8e-4bb1-9f0e-1c2d3e4f5a6b";

function ca(fields) {
  return {
    id: CA_ID,
    user_id: "u1",
    full_name: "Meera Shah",
    email: "meera@example.com",
    membership_no: "123456",
    cop_number: "COP-123",
    city: "Pune",
    languages: ["english"],
    specializations: ["itr"],
    capacity: 10,
    years_experience: 4,
    pro_bono_slots_per_month: 2,
    about: "",
    verification_status: "pending",
    rejection_reason: null,
    verified_at: null,
    has_certificate: true,
    updated_at: "2026-09-27T04:30:00Z",
    ...fields,
  };
}

describe("admin: Users & CAs", () => {
  it("lists CAs waiting for verification first", async () => {
    loginAs("admin");
    fakeApi({ "GET /api/v1/admin/cas?status=pending": [200, [ca()]] });
    renderApp("/admin/users");

    expect(await screen.findByRole("link", { name: "Review Meera Shah" })).toHaveAttribute(
      "href",
      `/admin/cas/${CA_ID}`,
    );
    expect(screen.getByRole("tab", { name: "Pending verification" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("filters all users by role and search", async () => {
    loginAs("admin");
    const fetchMock = fakeApi({
      "GET /api/v1/admin/cas?status=pending": [200, []],
      "GET /api/v1/admin/users": [200, { items: [], page: 1, page_size: 20, total: 0 }],
      "GET /api/v1/admin/users?role=ca&search=meera": [
        200,
        {
          items: [
            {
              id: "u1",
              full_name: "Meera Shah",
              email: "meera@example.com",
              role: "ca",
              is_active: true,
              email_verified: true,
              created_at: "2026-09-27T04:30:00Z",
            },
          ],
          page: 1,
          page_size: 20,
          total: 1,
        },
      ],
    });
    renderApp("/admin/users");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("tab", { name: "All users" }));
    await user.selectOptions(await screen.findByLabelText("Role"), "ca");
    await user.type(screen.getByLabelText("Name or email"), "meera");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByText("meera@example.com")).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Chartered Accountant")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([path]) => path.includes("role=ca&search=meera"))).toBe(true);
  });
});

describe("admin: reviewing a CA", () => {
  it("verifies a CA whose certificate is uploaded", async () => {
    loginAs("admin");
    vi.stubGlobal("URL", { ...URL, createObjectURL: () => "blob:cert", revokeObjectURL: () => {} });
    const fetchMock = fakeApi({
      [`GET /api/v1/admin/cas/${CA_ID}`]: [200, ca()],
      [`GET /api/v1/admin/cas/${CA_ID}/certificate`]: [200, {}],
      [`POST /api/v1/admin/cas/${CA_ID}/verify`]: [200, ca({ verification_status: "verified" })],
    });
    renderApp(`/admin/cas/${CA_ID}`);
    const user = userEvent.setup();

    expect(await screen.findByRole("link", { name: "Open the certificate" })).toHaveAttribute(
      "href",
      "blob:cert",
    );
    await user.click(screen.getByRole("button", { name: "Verify" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Verified. The CA has been emailed.",
    );
    expect(fetchMock.mock.calls.some(([path]) => path.endsWith("/verify"))).toBe(true);
  });

  it("rejects only with a reason", async () => {
    loginAs("admin");
    const fetchMock = fakeApi({
      [`GET /api/v1/admin/cas/${CA_ID}`]: [200, ca({ has_certificate: false })],
      [`POST /api/v1/admin/cas/${CA_ID}/reject`]: [200, ca({ verification_status: "rejected" })],
    });
    renderApp(`/admin/cas/${CA_ID}`);
    const user = userEvent.setup();

    const reject = await screen.findByRole("button", { name: "Reject" });
    expect(reject).toBeDisabled();
    expect(screen.getByRole("button", { name: "Verify" })).toBeDisabled(); // no certificate
    await user.type(screen.getByLabelText("Reason for rejecting"), "Upload your certificate.");
    await user.click(reject);

    expect(await screen.findByRole("status")).toHaveTextContent("Rejected.");
    const [, init] = fetchMock.mock.calls.find(([path]) => path.endsWith("/reject"));
    expect(JSON.parse(init.body)).toEqual({ reason: "Upload your certificate." });
  });
});

describe("admin dashboard", () => {
  it("shows the counts", async () => {
    loginAs("admin");
    fakeApi({
      "GET /api/v1/admin/dashboard": [200, { message: "Welcome, Test admin" }],
      "GET /api/v1/admin/stats": [
        200,
        {
          users_by_role: { business: 5, ca: 3, admin: 1 },
          businesses: 4,
          cas_by_status: { pending: 2, verified: 1, rejected: 0 },
          open_engagements: 6,
          filings_by_status: { upcoming: 30, overdue: 4, filed: 12 },
          filings_due_so_far: 20,
          filings_late: 5,
          overdue_rate: 25,
        },
      ],
    });
    renderApp("/admin");

    const pending = (await screen.findByText("CAs pending verification")).closest(
      "[data-slot=card]",
    );
    expect(within(pending).getByText("2")).toBeInTheDocument();
    expect(within(pending).getByRole("link", { name: "Review them" })).toHaveAttribute(
      "href",
      "/admin/users",
    );
    expect(screen.getByText("Open engagements").closest("[data-slot=card]")).toHaveTextContent("6");
    const rate = screen.getByText("Overdue rate").closest("[data-slot=card]");
    expect(rate).toHaveTextContent("25%");
    expect(rate).toHaveTextContent("5 of 20 filings due so far were not filed on time");
    expect(within(rate).getByText("Overdue").nextSibling).toHaveTextContent("4");
  });
});

describe("admin: suspend and reactivate", () => {
  const PAGE = (items) => [200, { items, page: 1, page_size: 20, total: items.length }];
  const person = (fields) => ({
    id: "u2",
    full_name: "Ravi Kumar",
    email: "ravi@example.com",
    role: "business",
    is_active: true,
    email_verified: true,
    created_at: "2026-09-20T04:30:00Z",
    ...fields,
  });

  it("suspends an account with a reason", async () => {
    loginAs("admin");
    vi.spyOn(window, "prompt").mockReturnValue(" Fake documents ");
    const fetchMock = fakeApi({
      "GET /api/v1/admin/cas?status=pending": [200, []],
      "GET /api/v1/admin/users": PAGE([person()]),
      "POST /api/v1/admin/users/u2/suspend": [200, person({ is_active: false })],
    });
    const user = userEvent.setup();
    renderApp("/admin/users");

    await user.click(await screen.findByRole("tab", { name: "All users" }));
    const row = (await screen.findByText("ravi@example.com")).closest("tr");
    expect(row).toHaveTextContent("Active");
    await user.click(within(row).getByRole("button", { name: "Suspend" }));

    const call = fetchMock.mock.calls.find(([url]) => url === "/api/v1/admin/users/u2/suspend");
    expect(JSON.parse(call[1].body)).toEqual({ reason: "Fake documents" });
    vi.restoreAllMocks();
  });

  it("reactivates a suspended account, and never offers to suspend yourself", async () => {
    const me = loginAs("admin");
    const fetchMock = fakeApi({
      "GET /api/v1/admin/cas?status=pending": [200, []],
      "GET /api/v1/admin/users": PAGE([
        person({ is_active: false }),
        person({ id: me.id, full_name: "Test admin", email: "admin@demo.local", role: "admin" }),
      ]),
      "POST /api/v1/admin/users/u2/reactivate": [200, person()],
    });
    const user = userEvent.setup();
    renderApp("/admin/users");

    await user.click(await screen.findByRole("tab", { name: "All users" }));
    const row = (await screen.findByText("ravi@example.com")).closest("tr");
    expect(row).toHaveTextContent("Suspended");
    await user.click(within(row).getByRole("button", { name: "Reactivate" }));
    const mine = screen.getByText("admin@demo.local").closest("tr");
    expect(within(mine).queryByRole("button")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === "/api/v1/admin/users/u2/reactivate")).toBe(
      true,
    );
  });
});

describe("admin: audit log", () => {
  it("lists admin actions with their details", async () => {
    loginAs("admin");
    fakeApi({
      "GET /api/v1/admin/audit-log?page=1": [
        200,
        {
          items: [
            {
              id: "a1",
              admin_name: "Admin One",
              action: "user.suspend",
              target_type: "user",
              target_id: "u2",
              target_name: "Ravi Kumar",
              details: { reason: "Fake documents", cancelled_requests: 2 },
              created_at: "2026-09-28T04:30:00Z",
            },
          ],
          page: 1,
          page_size: 20,
          total: 1,
        },
      ],
    });
    renderApp("/admin/audit");

    const row = (await screen.findByText("Suspended an account")).closest("tr");
    expect(row).toHaveTextContent("Admin One");
    expect(row).toHaveTextContent("Ravi Kumar");
    expect(row).toHaveTextContent("Reason: Fake documents · Requests cancelled: 2");
    expect(screen.getByRole("link", { name: "Audit log" })).toHaveAttribute("href", "/admin/audit");
  });
});
