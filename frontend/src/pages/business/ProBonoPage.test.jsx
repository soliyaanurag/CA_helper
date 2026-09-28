import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const URL = "/api/v1/marketplace/pro-bono";

function filing(fields) {
  return {
    id: "f1",
    form_code: "gstr_3b",
    period_label: "Aug 2026",
    due_date: "2026-09-20",
    blocked_reason: null,
    ...fields,
  };
}

const QUEUED = {
  id: "r1",
  status: "queued",
  note: "Small shop",
  created_at: "2026-09-28T05:00:00Z",
  business_name: "Asha Traders",
  filings: [filing()],
};

describe("business: Pro-bono help page", () => {
  it("is linked from the business sidebar", async () => {
    loginAs("business");
    fakeApi({});
    renderApp("/business");

    expect(await screen.findByRole("link", { name: "Pro-bono help" })).toHaveAttribute(
      "href",
      "/business/pro-bono",
    );
  });

  it("joins the queue with the ticked filings and a note", async () => {
    loginAs("business");
    const page = {
      eligible: true,
      reason: "Your business is a micro enterprise, so you can ask for a free CA.",
      request: null,
      filings: [
        filing(),
        filing({ id: "f2", period_label: "Jul 2026", blocked_reason: "Already filed." }),
      ],
    };
    const fetchMock = fakeApi({ [`GET ${URL}`]: [200, page], [`POST ${URL}`]: [201, QUEUED] });
    renderApp("/business/pro-bono");

    const user = userEvent.setup();
    await user.click(await screen.findByLabelText(/GSTR-3B Aug 2026/));
    expect(screen.getByLabelText(/GSTR-3B Jul 2026/)).toBeDisabled();
    await user.type(screen.getByLabelText("Note for the CA (optional)"), "Small shop");
    await user.click(screen.getByRole("button", { name: "Join the pro-bono queue" }));

    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === "POST");
    expect(JSON.parse(init.body)).toEqual({ compliance_item_ids: ["f1"], note: "Small shop" });
  });

  it("explains when the business is not eligible", async () => {
    loginAs("business");
    fakeApi({
      [`GET ${URL}`]: [
        200,
        {
          eligible: false,
          reason: "Free (pro-bono) help is for micro enterprises.",
          request: null,
          filings: [],
        },
      ],
    });
    renderApp("/business/pro-bono");

    expect(
      await screen.findByText("Free (pro-bono) help is for micro enterprises."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Join the pro-bono queue" }),
    ).not.toBeInTheDocument();
  });

  it("shows the queued request and leaves the queue", async () => {
    loginAs("business");
    const fetchMock = fakeApi({
      [`GET ${URL}`]: [200, { eligible: true, reason: "", request: QUEUED, filings: [] }],
      [`POST ${URL}/r1/cancel`]: [200, { ...QUEUED, status: "cancelled" }],
    });
    renderApp("/business/pro-bono");

    const user = userEvent.setup();
    expect(await screen.findByText("You are in the queue")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Leave the queue" }));

    expect(fetchMock.mock.calls.map(([path]) => path)).toContain(`${URL}/r1/cancel`);
  });
});
