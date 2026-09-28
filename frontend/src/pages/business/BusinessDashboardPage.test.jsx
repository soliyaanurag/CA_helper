import { screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { engagement } from "@/test/engagementData";
import { fakeApi, loginAs, renderApp } from "@/test/utils";

// "Today" is 27 Sep 2026.
beforeEach(() => vi.useFakeTimers({ toFake: ["Date"], now: new Date(2026, 8, 27) }));
afterEach(() => vi.useRealTimers());

function filing(fields) {
  return {
    id: fields.id,
    form_code: "gstr_3b",
    fy: "2026-27",
    period_label: "Aug 2026",
    due_date: "2026-09-30",
    status: "upcoming",
    filing_path: null,
    ...fields,
  };
}

const FILINGS = [
  filing({ id: "late", period_label: "Jul 2026", due_date: "2026-08-20", status: "overdue" }),
  filing({ id: "soon" }),
  filing({
    id: "ca",
    form_code: "gstr_1",
    due_date: "2026-10-11",
    status: "with_ca",
    filing_path: "ca",
  }),
  filing({ id: "later", form_code: "itr", period_label: "FY 2026-27", due_date: "2027-07-31" }),
];

// What GET /compliance/dashboard counts for FILINGS on 27 Sep 2026.
const DASHBOARD = {
  message: "Welcome, Test business",
  registered: true,
  next_deadline: FILINGS[1],
  due_this_month: 1,
  overdue: 1,
  with_ca: 1,
};

function api(engagements = []) {
  return fakeApi({
    "GET /api/v1/compliance/dashboard": [200, DASHBOARD],
    "GET /api/v1/compliance/items": [200, FILINGS],
    "GET /api/v1/marketplace/my-engagements": [200, engagements],
  });
}

describe("business dashboard", () => {
  it("shows the next deadline, due this month, overdue and with-a-CA numbers", async () => {
    loginAs("business");
    api();
    renderApp("/business");

    const next = (await screen.findByText("Next deadline")).closest("[data-slot=card]");
    expect(next).toHaveTextContent("GSTR-3B");
    expect(next).toHaveTextContent("In 3 days");
    expect(screen.getByText("Due this month").closest("[data-slot=card]")).toHaveTextContent("1");
    expect(screen.getByText("Overdue").closest("[data-slot=card]")).toHaveTextContent("1");
    expect(screen.getByText("With a CA").closest("[data-slot=card]")).toHaveTextContent("1");
  });

  it("lists what to do", async () => {
    loginAs("business");
    api([engagement({ status: "quoted" })]);
    renderApp("/business");

    const todo = (await screen.findByRole("heading", { name: "To do" })).closest("section");
    expect(
      within(todo).getByText("Meera Shah sent a quote: accept or reject it"),
    ).toBeInTheDocument();
    expect(within(todo).getByText("Check 1 overdue filings")).toBeInTheDocument();
    expect(within(todo).getByText(/Decide how to file GSTR-3B Aug 2026/)).toHaveAttribute(
      "href",
      "/business/compliance/soon",
    );
  });

  it("asks an unregistered business to register", async () => {
    loginAs("business");
    fakeApi({
      "GET /api/v1/compliance/dashboard": [200, { message: "Welcome, Test business" }],
      "GET /api/v1/compliance/items": [404, { error: { code: "BUSINESS_NOT_FOUND", message: "" } }],
    });
    renderApp("/business");

    expect(await screen.findByRole("link", { name: "Register your business" })).toBeInTheDocument();
  });
});
