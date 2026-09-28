import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const QUEUE_URL = "/api/v1/marketplace/pro-bono-queue";

const REQUEST = {
  id: "r1",
  status: "queued",
  note: "Small shop",
  created_at: "2026-09-28T05:00:00Z",
  business_name: "Asha Traders",
  filings: [
    {
      id: "f1",
      form_code: "gstr_3b",
      period_label: "Aug 2026",
      due_date: "2026-09-20",
      blocked_reason: null,
    },
  ],
};

describe("CA: Pro-bono queue page", () => {
  it("is linked from the CA sidebar", async () => {
    loginAs("ca");
    fakeApi({});
    renderApp("/ca");

    expect(await screen.findByRole("link", { name: "Pro-bono queue" })).toHaveAttribute(
      "href",
      "/ca/pro-bono",
    );
  });

  it("takes a request when the CA has a free slot", async () => {
    loginAs("ca");
    const fetchMock = fakeApi({
      [`GET ${QUEUE_URL}`]: [
        200,
        { pledged: 2, used_this_month: 1, verified: true, requests: [REQUEST] },
      ],
      "POST /api/v1/marketplace/pro-bono/r1/accept": [200, {}],
    });
    renderApp("/ca/pro-bono");

    expect(await screen.findByText("Asha Traders")).toBeInTheDocument();
    expect(screen.getByText(/Free slots this month/)).toHaveTextContent("1 of 2");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Take this request (free)" }));

    expect(fetchMock.mock.calls.map(([path]) => path)).toContain(
      "/api/v1/marketplace/pro-bono/r1/accept",
    );
  });

  it("cannot take requests without a pledge", async () => {
    loginAs("ca");
    fakeApi({
      [`GET ${QUEUE_URL}`]: [
        200,
        { pledged: 0, used_this_month: 0, verified: true, requests: [REQUEST] },
      ],
    });
    renderApp("/ca/pro-bono");

    expect(await screen.findByText(/Set your free \(pro-bono\) slots/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Take this request (free)" })).toBeDisabled();
  });
});
