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

// GET /alerts/penalties: one overdue filing, its late fee not confirmed yet.
const EXPOSURE = {
  total_late_fees: "0.00",
  overdue_count: 1,
  estimated_count: 0,
  pending_count: 1,
  label: "Estimate (rules pending verification)",
  items: [],
};

function api(engagements = [], exposure = EXPOSURE, requests = []) {
  return fakeApi({
    "GET /api/v1/compliance/dashboard": [200, DASHBOARD],
    "GET /api/v1/compliance/items": [200, FILINGS],
    "GET /api/v1/marketplace/my-engagements": [200, engagements],
    "GET /api/v1/alerts/penalties": [200, exposure],
    "GET /api/v1/ca-workspace/document-requests": [200, requests],
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

  it("lists the documents a CA asked for first", async () => {
    loginAs("business");
    api([], EXPOSURE, [
      {
        id: "r1",
        compliance_item_id: "f9",
        form_code: "gstr_1",
        period_label: "Q2 2026-27",
        checklist_key: "hsn_summary",
        message: "The HSN summary please",
        status: "open",
        created_at: "2026-09-25T10:00:00Z",
        fulfilled_at: null,
        document_id: null,
        ca_name: "Meera Shah",
      },
    ]);
    renderApp("/business");

    const todo = (await screen.findByRole("heading", { name: "To do" })).closest("section");
    const first = await within(todo).findByText(
      "Meera Shah asked for a document for GSTR-1 Q2 2026-27: The HSN summary please",
    );
    expect(first).toHaveAttribute("href", "/business/compliance/f9");
    expect(within(todo).getAllByRole("link")[0]).toBe(first);
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

  it("shows the penalty exposure of overdue filings, labelled as an estimate", async () => {
    loginAs("business");
    api();
    renderApp("/business");

    const card = (await screen.findByText(/Penalty exposure/)).closest("[data-slot=card]");
    expect(card).toHaveTextContent("Estimate (rules pending verification)");
    expect(card).toHaveTextContent("Not available yet");
    expect(card).toHaveTextContent("1 of 1 have no confirmed rule yet");
  });

  it("adds up the confirmed late fees", async () => {
    loginAs("business");
    api([], { ...EXPOSURE, total_late_fees: "1500.00", estimated_count: 1, pending_count: 0 });
    renderApp("/business");

    const card = (await screen.findByText(/Penalty exposure/)).closest("[data-slot=card]");
    expect(card).toHaveTextContent("₹1,500");
    expect(card).not.toHaveTextContent("no confirmed rule");
  });
});
