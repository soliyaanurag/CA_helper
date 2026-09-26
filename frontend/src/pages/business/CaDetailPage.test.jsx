import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const CA_ID = "0b5f0b8e-4a8e-4bb1-9f0e-1c2d3e4f5a6b";
const LIST_URL = "/api/v1/marketplace/cas";
const DETAIL_URL = `${LIST_URL}/${CA_ID}`;

const CA = {
  id: CA_ID,
  full_name: "Priya Iyer",
  membership_no: "900001",
  city: "Chennai",
  languages: ["english", "tamil"],
  specializations: ["itr", "tds_24q"],
  years_experience: 12,
  about: "Income tax for salaried people.",
};

const GST_SERVICE = {
  id: "11111111-1111-4111-8111-111111111111",
  code: "gstr_3b",
  name: "GSTR-3B filing",
  description: "Summary GST return.",
  unit: "per_return",
  ca_count: 3,
  min_price: "600.00",
  median_price: "700.00",
  max_price: "1000.00",
  price: "650.00",
};
const AUDIT_SERVICE = {
  id: "22222222-2222-4222-8222-222222222222",
  code: "tax_audit",
  name: "Tax audit",
  description: "Audit for one year.",
  unit: "per_year",
  ca_count: 1,
  min_price: null,
  median_price: null,
  max_price: null,
  price: "25000.00",
};

describe("CA detail page", () => {
  it("shows the CA's details and every service with its fee", async () => {
    loginAs("business");
    fakeApi({ [`GET ${DETAIL_URL}`]: [200, { ...CA, services: [GST_SERVICE, AUDIT_SERVICE] }] });
    renderApp(`/business/marketplace/${CA_ID}`);

    expect(await screen.findByRole("heading", { name: "Priya Iyer" })).toBeInTheDocument();
    expect(screen.getByText("Income tax for salaried people.")).toBeInTheDocument();
    expect(screen.getByText("English, Tamil")).toBeInTheDocument();

    const gstRow = screen.getByText("GSTR-3B filing").closest("tr");
    expect(gstRow).toHaveTextContent("₹650 per return");
    expect(gstRow).toHaveTextContent("Below the median");
    expect(gstRow).toHaveTextContent("₹600 – ₹1,000, median ₹700 (3 CAs)");
    const auditRow = screen.getByText("Tax audit").closest("tr");
    expect(auditRow).toHaveTextContent("₹25,000 per year");
    expect(auditRow).toHaveTextContent("Not enough data yet");
  });

  it("says so when the CA has no prices yet", async () => {
    loginAs("business");
    fakeApi({ [`GET ${DETAIL_URL}`]: [200, { ...CA, services: [] }] });
    renderApp(`/business/marketplace/${CA_ID}`);

    expect(await screen.findByText("This CA has not listed any prices yet.")).toBeInTheDocument();
  });

  it("shows the API's message for a CA that is not listed", async () => {
    loginAs("business");
    fakeApi({
      [`GET ${DETAIL_URL}`]: [
        404,
        { error: { code: "CA_NOT_FOUND", message: "This CA is not listed on the marketplace." } },
      ],
    });
    renderApp(`/business/marketplace/${CA_ID}`);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This CA is not listed on the marketplace.",
    );
  });

  it("opens when the card is clicked and goes back to the same filtered results", async () => {
    loginAs("business");
    fakeApi({
      [`GET ${LIST_URL}?city=Chennai`]: [
        200,
        { items: [{ ...CA, price: null }], page: 1, page_size: 20, total: 1 },
      ],
      [`GET ${DETAIL_URL}`]: [200, { ...CA, services: [] }],
    });
    const router = renderApp("/business/marketplace?city=Chennai");

    const user = userEvent.setup();
    // Click anywhere on the card, here on the CA's city line.
    await user.click(await screen.findByText(/Chennai · 12 years/));

    expect(await screen.findByText("This CA has not listed any prices yet.")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(`/business/marketplace/${CA_ID}`);

    await user.click(screen.getByRole("link", { name: "← Back to results" }));

    expect(router.state.location.search).toBe("?city=Chennai");
    expect(await screen.findByRole("heading", { name: "Priya Iyer" })).toBeInTheDocument();
  });
});
