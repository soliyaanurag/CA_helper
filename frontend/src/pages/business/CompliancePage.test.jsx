import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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

describe("compliance calendar page", () => {
  it("lists the filings with readable names and dates", async () => {
    loginAs("business");
    fakeApi({ [`GET ${URL}`]: [200, FILINGS] });
    renderApp("/business/compliance");

    const rows = await screen.findAllByRole("row");
    expect(rows).toHaveLength(3); // the header + 2 filings
    expect(within(rows[1]).getByText("GSTR-1")).toBeInTheDocument();
    expect(within(rows[1]).getByText("13 Oct 2026")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Income tax return (ITR)")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Upcoming")).toBeInTheDocument();
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
