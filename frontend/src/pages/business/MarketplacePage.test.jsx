import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const URL = "/api/v1/marketplace/cas";

function ca(fields) {
  return {
    id: crypto.randomUUID(),
    full_name: "Priya Iyer",
    membership_no: "900001",
    city: "Chennai",
    languages: ["english", "tamil"],
    specializations: ["itr", "tds_24q"],
    years_experience: 12,
    about: "Income tax for salaried people.",
    ...fields,
  };
}

function page(items, fields = {}) {
  return [200, { items, page: 1, page_size: 20, total: items.length, ...fields }];
}

describe("Find a CA page", () => {
  it("lists verified CAs with their tags and languages", async () => {
    loginAs("business");
    fakeApi({ [`GET ${URL}`]: page([ca(), ca({ full_name: "Rahul Mehta" })]) });
    renderApp("/business/marketplace");

    expect(await screen.findByRole("heading", { name: "Priya Iyer" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Rahul Mehta" })).toBeInTheDocument();
    expect(screen.getByText("2 CAs found")).toBeInTheDocument();
    expect(screen.getAllByText("Income tax return (ITR)")[0]).toBeInTheDocument();
    expect(screen.getAllByText("English, Tamil")).toHaveLength(2);
  });

  it("applies filters from the URL and from the search form", async () => {
    loginAs("business");
    const fetchMock = fakeApi({
      [`GET ${URL}?specialization=itr`]: page([ca()]),
      [`GET ${URL}?specialization=itr&language=hindi&city=Pune`]: page([]),
    });
    renderApp("/business/marketplace?specialization=itr");

    expect(await screen.findByRole("heading", { name: "Priya Iyer" })).toBeInTheDocument();
    expect(screen.getByLabelText("Specialization")).toHaveValue("itr");

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Language"), "hindi");
    await user.type(screen.getByLabelText("City"), "Pune");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByText("No verified CAs match these filters.")).toBeInTheDocument();
    expect(fetchMock.mock.calls.map(([path]) => path)).toContain(
      `${URL}?specialization=itr&language=hindi&city=Pune`,
    );
  });

  it("pages through the results", async () => {
    loginAs("business");
    fakeApi({
      [`GET ${URL}`]: page([ca()], { total: 25 }),
      [`GET ${URL}?page=2`]: page([ca({ full_name: "Vikram Rao" })], { page: 2, total: 25 }),
    });
    renderApp("/business/marketplace");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Next" }));

    expect(await screen.findByRole("heading", { name: "Vikram Rao" })).toBeInTheDocument();
    expect(screen.getByText("Page 2 of 2")).toBeInTheDocument();
  });

  it("shows the typical fee and each CA's price for the chosen service", async () => {
    loginAs("business");
    fakeApi({
      "GET /api/v1/marketplace/services": [
        200,
        [
          {
            id: "11111111-1111-4111-8111-111111111111",
            code: "gstr_3b",
            name: "GSTR-3B filing",
            description: "Summary GST return.",
            unit: "per_return",
            ca_count: 3,
            min_price: "600.00",
            median_price: "700.00",
            max_price: "1000.00",
          },
        ],
      ],
      [`GET ${URL}?service=gstr_3b`]: page([ca({ price: "650.00" })]),
    });
    renderApp("/business/marketplace?service=gstr_3b");

    expect(await screen.findByText("₹650 per return · Below the median")).toBeInTheDocument();
    expect(
      screen.getByText("₹600 – ₹1,000, median ₹700 (3 CAs) · per return", { exact: false }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Service")).toHaveValue("gstr_3b");
  });

  it("shows an API error", async () => {
    loginAs("business");
    fakeApi({ [`GET ${URL}`]: [500, { error: { code: "X", message: "Something broke." } }] });
    renderApp("/business/marketplace");

    expect(await screen.findByRole("alert")).toHaveTextContent("Something broke.");
  });
});
