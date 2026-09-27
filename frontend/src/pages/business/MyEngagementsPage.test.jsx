import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ENGAGEMENT_ID, engagement } from "@/test/engagementData";
import { fakeApi, loginAs, renderApp } from "@/test/utils";

const LIST_URL = "/api/v1/marketplace/my-engagements";
const ACTION_URL = `/api/v1/marketplace/engagements/${ENGAGEMENT_ID}`;

const QUOTED = engagement({
  status: "quoted",
  quote_reason: "Your August has 400 invoices.",
  items: engagement().items.map((item) => ({ ...item, quoted_price: "1000.00" })),
});

describe("business: My engagements page", () => {
  it("is linked from the business sidebar", async () => {
    loginAs("business");
    fakeApi({});
    renderApp("/business");

    expect(await screen.findByRole("link", { name: "My engagements" })).toHaveAttribute(
      "href",
      "/business/engagements",
    );
  });

  it("shows a quote with its reason, prices and totals", async () => {
    loginAs("business");
    fakeApi({ [`GET ${LIST_URL}`]: [200, [QUOTED]] });
    renderApp("/business/engagements");

    const section = (await screen.findByRole("heading", { name: "Quote to review" })).closest(
      "section",
    );
    expect(within(section).getByText("Meera Shah")).toBeInTheDocument();
    expect(within(section).getByText("Quote sent")).toBeInTheDocument();
    expect(within(section).getByText(/400 invoices/)).toBeInTheDocument();
    expect(within(section).getByText("₹1,400")).toBeInTheDocument(); // listed total
    expect(within(section).getByText("₹2,000")).toBeInTheDocument(); // quoted total
  });

  it("accepts a quote", async () => {
    loginAs("business");
    const fetchMock = fakeApi({
      [`GET ${LIST_URL}`]: [200, [QUOTED]],
      [`POST ${ACTION_URL}/accept-quote`]: [200, engagement({ status: "active" })],
    });
    renderApp("/business/engagements");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Accept quote" }));

    expect(fetchMock.mock.calls.map(([path]) => path)).toContain(`${ACTION_URL}/accept-quote`);
  });

  it("withdraws an unanswered request", async () => {
    loginAs("business");
    const fetchMock = fakeApi({
      [`GET ${LIST_URL}`]: [200, [engagement()]],
      [`POST ${ACTION_URL}/withdraw`]: [200, engagement({ status: "cancelled" })],
    });
    renderApp("/business/engagements");

    const user = userEvent.setup();
    expect(await screen.findByRole("heading", { name: "Waiting for the CA" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Withdraw request" }));

    expect(fetchMock.mock.calls.map(([path]) => path)).toContain(`${ACTION_URL}/withdraw`);
    expect(screen.queryByRole("button", { name: "Accept quote" })).not.toBeInTheDocument();
  });

  it("shows an action's error", async () => {
    loginAs("business");
    fakeApi({
      [`GET ${LIST_URL}`]: [200, [QUOTED]],
      [`POST ${ACTION_URL}/reject-quote`]: [
        409,
        { error: { code: "INVALID_STATUS", message: "This engagement is active." } },
      ],
    });
    renderApp("/business/engagements");

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Reject quote" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This engagement is active.");
  });

  it("shows finished engagements without actions", async () => {
    loginAs("business");
    fakeApi({ [`GET ${LIST_URL}`]: [200, [engagement({ status: "declined" })]] });
    renderApp("/business/engagements");

    expect(await screen.findByRole("heading", { name: "Finished" })).toBeInTheDocument();
    expect(screen.getByText("Declined")).toBeInTheDocument();
    for (const name of ["Accept quote", "Reject quote", "Withdraw request"]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });
});
