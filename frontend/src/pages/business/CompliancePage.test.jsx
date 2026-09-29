import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const URL = "/api/v1/compliance/items";

const FILINGS = [
  {
    id: "a1",
    form_code: "gstr_1",
    fy: "2026-27",
    period_label: "Q2 2026-27",
    period_start: "2026-07-01",
    period_end: "2026-09-30",
    due_date: "2026-10-13",
    status: "upcoming",
    filing_path: null,
  },
  {
    id: "a2",
    form_code: "itr",
    fy: "2026-27",
    period_label: "FY 2026-27",
    period_start: "2026-04-01",
    period_end: "2027-03-31",
    due_date: "2027-07-31",
    status: "upcoming",
    filing_path: null,
  },
];

// "Today" is 27 Sep 2026 in these tests: what counts as past depends on it.
beforeEach(() => vi.useFakeTimers({ toFake: ["Date"], now: new Date(2026, 8, 27) }));
afterEach(() => vi.useRealTimers());

const OVERDUE = {
  ...FILINGS[0],
  id: "a0",
  period_label: "Q1 2026-27",
  period_start: "2026-04-01",
  period_end: "2026-06-30",
  due_date: "2026-07-13",
  status: "overdue",
};

describe("compliance calendar page", () => {
  it("lists the filings with readable names and dates", async () => {
    loginAs("business");
    fakeApi({ [`GET ${URL}`]: [200, FILINGS] });
    renderApp("/business/compliance");

    const rows = await screen.findAllByRole("row");
    expect(rows).toHaveLength(4); // one table per month: a header + a filing each
    expect(within(rows[1]).getByText("GSTR-1")).toBeInTheDocument();
    expect(within(rows[1]).getByText("13 Oct 2026")).toBeInTheDocument();
    expect(within(rows[3]).getByText("Income tax return (ITR)")).toBeInTheDocument();
    expect(within(rows[3]).getByText("Upcoming")).toBeInTheDocument();
  });

  it("shows a TDS return of this year under its new name", async () => {
    loginAs("business");
    const tds = { ...FILINGS[0], id: "t1", form_code: "tds_24q", period_label: "Q2 2026-27" };
    fakeApi({ [`GET ${URL}`]: [200, [tds]] });
    renderApp("/business/compliance");

    expect(await screen.findByText("Form 138 (earlier 24Q)")).toBeInTheDocument();
  });

  it("groups by month, with the days left", async () => {
    loginAs("business");
    fakeApi({ [`GET ${URL}`]: [200, FILINGS] });
    renderApp("/business/compliance");

    expect(await screen.findByRole("heading", { name: "October 2026" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "July 2027" })).toBeInTheDocument();
    expect(screen.getByText("In 16 days")).toBeInTheDocument(); // 27 Sep -> 13 Oct
  });

  it("shows past due dates in their own section", async () => {
    loginAs("business");
    fakeApi({ [`GET ${URL}`]: [200, [OVERDUE, ...FILINGS]] });
    renderApp("/business/compliance");

    const earlier = (
      await screen.findByRole("heading", { name: "Earlier this year: due dates already passed" })
    ).closest("section");
    expect(within(earlier).getByText("Q1 2026-27")).toBeInTheDocument();
    expect(within(earlier).getByText("Overdue")).toBeInTheDocument();
    expect(within(earlier).getByText("76 days ago")).toBeInTheDocument();
    expect(
      within(earlier).getByText("If you already filed this, you'll be able to mark it as filed."),
    ).toBeInTheDocument();
  });

  it("filters by form and status", async () => {
    loginAs("business");
    fakeApi({ [`GET ${URL}`]: [200, [OVERDUE, ...FILINGS]] });
    renderApp("/business/compliance");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "ITR" }));
    expect(screen.queryByText("GSTR-1")).not.toBeInTheDocument();
    expect(screen.getByText("Income tax return (ITR)")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "All", pressed: false }));
    await user.click(screen.getByRole("button", { name: "Overdue" }));
    expect(screen.getByText("Q1 2026-27")).toBeInTheDocument();
    expect(screen.queryByText("Q2 2026-27")).not.toBeInTheDocument();
  });

  it("sends a business that is not registered to the profile page", async () => {
    loginAs("business");
    fakeApi({
      [`GET ${URL}`]: [404, { error: { code: "BUSINESS_NOT_FOUND", message: "Register first." } }],
    });
    renderApp("/business/compliance");

    expect(await screen.findByRole("link", { name: "Register your business" })).toHaveAttribute(
      "href",
      "/business/onboarding",
    );
  });
});
