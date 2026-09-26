import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const SERVICES = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    code: "gstr_3b",
    name: "GSTR-3B filing",
    description: "Summary GST return.",
    unit: "per_return",
    ca_count: 3,
    min_price: "600.00",
    median_price: "700.00",
    max_price: "100000.00",
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    code: "tax_audit",
    name: "Tax audit",
    description: "Audit for one year.",
    unit: "per_year",
    ca_count: 1,
    min_price: null,
    median_price: null,
    max_price: null,
  },
];

describe("Typical fees page", () => {
  it("lists each service's range, or says there is not enough data", async () => {
    loginAs("business");
    fakeApi({ "GET /api/v1/marketplace/services": [200, SERVICES] });
    renderApp("/business/fees");

    const gstRow = (await screen.findByText("GSTR-3B filing")).closest("tr");
    expect(gstRow).toHaveTextContent("₹600");
    expect(gstRow).toHaveTextContent("₹700");
    expect(gstRow).toHaveTextContent("₹1,00,000"); // Indian digit grouping
    expect(screen.getByText("Tax audit").closest("tr")).toHaveTextContent("Not enough data yet");
  });

  it("links each service to Find a CA with that service chosen", async () => {
    loginAs("business");
    fakeApi({ "GET /api/v1/marketplace/services": [200, SERVICES] });
    renderApp("/business/fees");

    await screen.findByText("GSTR-3B filing"); // the table has loaded
    const links = screen.getAllByRole("link", { name: "Find a CA" });
    // The sidebar has a "Find a CA" link too; the table's links carry the service.
    expect(links.map((link) => link.getAttribute("href"))).toContain(
      "/business/marketplace?service=gstr_3b",
    );
  });

  it("is linked from the business sidebar", async () => {
    loginAs("business");
    fakeApi({});
    renderApp("/business");

    expect(await screen.findByRole("link", { name: "Typical fees" })).toHaveAttribute(
      "href",
      "/business/fees",
    );
  });
});
