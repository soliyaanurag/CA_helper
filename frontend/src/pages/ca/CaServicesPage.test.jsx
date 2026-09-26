import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const PROFILE_URL = "/api/v1/marketplace/ca-profile";
const SERVICES_URL = "/api/v1/marketplace/services";
const MENU_URL = "/api/v1/marketplace/ca-services";

const GST = {
  id: "11111111-1111-4111-8111-111111111111",
  code: "gstr_3b",
  name: "GSTR-3B filing",
  description: "Summary GST return.",
  unit: "per_return",
  ca_count: 3,
  min_price: "600.00",
  median_price: "700.00",
  max_price: "1000.00",
};
const AUDIT = {
  id: "22222222-2222-4222-8222-222222222222",
  code: "tax_audit",
  name: "Tax audit",
  description: "Audit for one year.",
  unit: "per_year",
  ca_count: 1,
  min_price: null,
  median_price: null,
  max_price: null,
};
const PROFILE = { id: "p1", verification_status: "verified" };

function api(extra = {}) {
  return fakeApi({
    [`GET ${PROFILE_URL}`]: [200, PROFILE],
    [`GET ${SERVICES_URL}`]: [200, [GST, AUDIT]],
    [`GET ${MENU_URL}`]: [200, { items: [{ service_id: GST.id, price: "750.00" }] }],
    ...extra,
  });
}

describe("CA services & prices page", () => {
  it("is linked from the CA sidebar", async () => {
    loginAs("ca");
    api();
    renderApp("/ca");

    expect(await screen.findByRole("link", { name: "Services & prices" })).toHaveAttribute(
      "href",
      "/ca/services",
    );
  });

  it("shows the saved prices and the typical ranges", async () => {
    loginAs("ca");
    api();
    renderApp("/ca/services");

    expect(await screen.findByLabelText("GSTR-3B filing")).toBeChecked();
    expect(screen.getByLabelText("Price for GSTR-3B filing")).toHaveValue("750");
    expect(screen.getByText("Typical: ₹600 – ₹1,000, median ₹700 (3 CAs)")).toBeInTheDocument();
    expect(screen.getByText("Above the median")).toBeInTheDocument();
    expect(screen.getByLabelText("Tax audit")).not.toBeChecked();
    expect(screen.getByLabelText("Price for Tax audit")).toBeDisabled();
    expect(screen.getByText("Typical: Not enough data yet")).toBeInTheDocument();
  });

  it("saves the ticked services with their prices", async () => {
    loginAs("ca");
    const saved = {
      items: [
        { service_id: GST.id, price: "750.00" },
        { service_id: AUDIT.id, price: "20000.00" },
      ],
    };
    const fetchMock = api({ [`PUT ${MENU_URL}`]: [200, saved] });
    renderApp("/ca/services");

    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("Tax audit"));
    await user.type(screen.getByLabelText("Price for Tax audit"), "20000");
    await user.click(screen.getByRole("button", { name: "Save prices" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Prices saved.");
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === "PUT");
    expect(JSON.parse(init.body)).toEqual({
      items: [
        { service_id: GST.id, price: "750" },
        { service_id: AUDIT.id, price: "20000" },
      ],
    });
  });

  it("checks prices before sending anything", async () => {
    loginAs("ca");
    const fetchMock = api();
    renderApp("/ca/services");

    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("Tax audit"));
    await user.click(screen.getByRole("button", { name: "Save prices" }));

    expect(await screen.findByText("Enter a price from 1 to 10,00,000.")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === "PUT")).toBe(false);
  });

  it("asks for a profile first", async () => {
    loginAs("ca");
    api({
      [`GET ${PROFILE_URL}`]: [
        404,
        { error: { code: "CA_PROFILE_NOT_FOUND", message: "Not completed." } },
      ],
      [`GET ${MENU_URL}`]: [200, { items: [] }],
    });
    renderApp("/ca/services");

    expect(await screen.findByText("Complete your profile first")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Complete profile" })).toHaveAttribute(
      "href",
      "/ca/profile",
    );
  });

  it("tells an unverified CA when businesses will see the prices", async () => {
    loginAs("ca");
    api({ [`GET ${PROFILE_URL}`]: [200, { ...PROFILE, verification_status: "pending" }] });
    renderApp("/ca/services");

    expect(
      await screen.findByText(
        "Businesses see your prices once an admin has verified your profile.",
      ),
    ).toBeInTheDocument();
  });
});
