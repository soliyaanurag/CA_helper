import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ENGAGEMENT_ID, engagement } from "@/test/engagementData";
import { fakeApi, loginAs, renderApp } from "@/test/utils";

const LIST_URL = "/api/v1/marketplace/ca-engagements";
const ACTION_URL = `/api/v1/marketplace/engagements/${ENGAGEMENT_ID}`;

function sentBody(fetchMock, path) {
  const [, init] = fetchMock.mock.calls.find(([url]) => url === path);
  return init.body === undefined ? undefined : JSON.parse(init.body);
}

describe("CA: My engagements page", () => {
  it("is linked from the CA sidebar", async () => {
    loginAs("ca");
    fakeApi({});
    renderApp("/ca");

    expect(await screen.findByRole("link", { name: "My engagements" })).toHaveAttribute(
      "href",
      "/ca/engagements",
    );
  });

  it("shows a new request with the business and its filings", async () => {
    loginAs("ca");
    fakeApi({ [`GET ${LIST_URL}`]: [200, [engagement()]] });
    renderApp("/ca/engagements");

    expect(await screen.findByRole("heading", { name: "New requests" })).toBeInTheDocument();
    expect(screen.getByText("Asha Traders")).toBeInTheDocument();
    expect(screen.getByText("GSTR-3B filing")).toBeInTheDocument();
    expect(screen.getByText("₹1,400")).toBeInTheDocument();
  });

  it("accepts a request", async () => {
    loginAs("ca");
    const fetchMock = fakeApi({
      [`GET ${LIST_URL}`]: [200, [engagement()]],
      [`POST ${ACTION_URL}/accept`]: [200, engagement({ status: "active" })],
    });
    renderApp("/ca/engagements");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Accept at listed prices" }));

    expect(fetchMock.mock.calls.map(([path]) => path)).toContain(`${ACTION_URL}/accept`);
  });

  it("sends a quote with a new price per filing and a reason", async () => {
    loginAs("ca");
    const fetchMock = fakeApi({
      [`GET ${LIST_URL}`]: [200, [engagement()]],
      [`POST ${ACTION_URL}/quote`]: [200, engagement({ status: "quoted" })],
    });
    renderApp("/ca/engagements");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Send a quote" }));
    const firstPrice = screen.getByLabelText("GSTR-3B Aug 2026");
    expect(firstPrice).toHaveValue("800"); // starts at the listed price
    await user.clear(firstPrice);
    await user.type(firstPrice, "1200");
    await user.type(screen.getByLabelText("Reason (the business sees it)"), "400 invoices.");
    await user.click(screen.getByRole("button", { name: "Send quote" }));

    expect(sentBody(fetchMock, `${ACTION_URL}/quote`)).toEqual({
      reason: "400 invoices.",
      prices: [
        { engagement_item_id: "i1", price: "1200" },
        { engagement_item_id: "i2", price: "600" },
      ],
    });
  });

  it("needs a reason for a quote", async () => {
    loginAs("ca");
    const fetchMock = fakeApi({ [`GET ${LIST_URL}`]: [200, [engagement()]] });
    renderApp("/ca/engagements");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Send a quote" }));
    await user.click(screen.getByRole("button", { name: "Send quote" }));

    expect(screen.getByText("Tell the business why the price is different.")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
  });

  it("declines a request and completes an active one", async () => {
    loginAs("ca");
    const active = engagement({ id: "e2", status: "active" });
    const fetchMock = fakeApi({
      [`GET ${LIST_URL}`]: [200, [engagement(), active]],
      [`POST ${ACTION_URL}/decline`]: [200, engagement({ status: "declined" })],
      "POST /api/v1/marketplace/engagements/e2/complete": [200, { ...active, status: "completed" }],
    });
    renderApp("/ca/engagements");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Decline" }));
    await user.click(screen.getByRole("button", { name: "Mark as completed" }));

    const paths = fetchMock.mock.calls.map(([path]) => path);
    expect(paths).toContain(`${ACTION_URL}/decline`);
    expect(paths).toContain("/api/v1/marketplace/engagements/e2/complete");
  });
});
