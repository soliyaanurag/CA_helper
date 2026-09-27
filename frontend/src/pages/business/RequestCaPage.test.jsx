import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { CA_ID, engagement } from "@/test/engagementData";
import { fakeApi, loginAs, renderApp } from "@/test/utils";

const CA_URL = `/api/v1/marketplace/cas/${CA_ID}`;
const FILINGS_URL = `${CA_URL}/requestable-filings`;

const CA = {
  id: CA_ID,
  full_name: "Meera Shah",
  membership_no: "900001",
  city: "Pune",
  languages: ["english"],
  specializations: ["gstr_3b"],
  years_experience: 5,
  about: "",
  services: [],
};

function filing(fields) {
  return {
    id: "f1",
    form_code: "gstr_3b",
    period_label: "Aug 2026",
    due_date: "2026-09-20",
    status: "upcoming",
    options: [{ service_id: "s-3b", name: "GSTR-3B filing", price: "800.00" }],
    blocked_reason: null,
    ...fields,
  };
}

const FILINGS = [
  filing(),
  filing({
    id: "f2",
    form_code: "itr",
    period_label: "FY 2025-26",
    due_date: "2026-10-31",
    options: [
      { service_id: "s-itr4", name: "ITR filing: presumptive income (ITR-4)", price: "1200.00" },
      {
        service_id: "s-itr3",
        name: "ITR filing: business or profession (ITR-3)",
        price: "2500.00",
      },
    ],
  }),
  filing({
    id: "f3",
    form_code: "tds_26q",
    period_label: "Q2 2026-27",
    options: [],
    blocked_reason: "This CA has not listed a price for this filing.",
  }),
];

describe("Request this CA page", () => {
  it("is opened from the CA's page", async () => {
    loginAs("business");
    fakeApi({ [`GET ${CA_URL}`]: [200, CA] });
    renderApp(`/business/marketplace/${CA_ID}`);

    expect(await screen.findByRole("link", { name: "Request this CA" })).toHaveAttribute(
      "href",
      `/business/marketplace/${CA_ID}/request`,
    );
  });

  it("sends the ticked filings with the chosen services", async () => {
    loginAs("business");
    const fetchMock = fakeApi({
      [`GET ${CA_URL}`]: [200, CA],
      [`GET ${FILINGS_URL}`]: [200, FILINGS],
      "POST /api/v1/marketplace/engagements": [201, engagement()],
      "GET /api/v1/marketplace/my-engagements": [200, [engagement()]],
    });
    const router = renderApp(`/business/marketplace/${CA_ID}/request`);

    const user = userEvent.setup();
    await user.click(await screen.findByLabelText(/GSTR-3B Aug 2026/));
    await user.click(screen.getByLabelText(/ITR\) FY 2025-26/));
    await user.selectOptions(screen.getByLabelText("Service for FY 2025-26"), "s-itr3");

    expect(screen.getByText("Total at the listed prices: ₹3,300")).toBeInTheDocument();
    expect(screen.getByLabelText(/Q2 2026-27/)).toBeDisabled();
    expect(screen.getByText("This CA has not listed a price for this filing.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(await screen.findByText(/Your request was sent/)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/business/engagements");
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === "POST");
    expect(JSON.parse(init.body)).toEqual({
      ca_profile_id: CA_ID,
      items: [
        { compliance_item_id: "f1", service_id: "s-3b" },
        { compliance_item_id: "f2", service_id: "s-itr3" },
      ],
    });
  });

  it("keeps Send disabled until a filing is ticked, and says why", async () => {
    loginAs("business");
    fakeApi({
      [`GET ${CA_URL}`]: [200, CA],
      [`GET ${FILINGS_URL}`]: [200, FILINGS],
    });
    renderApp(`/business/marketplace/${CA_ID}/request`);

    const send = await screen.findByRole("button", { name: "Send request" });
    expect(send).toBeDisabled();
    expect(screen.getByText(/Tick at least one filing\./)).toBeInTheDocument();
    expect(screen.getByText(/The CA has 48 hours to respond\./)).toBeInTheDocument();

    await userEvent.setup().click(screen.getByLabelText(/GSTR-3B Aug 2026/));

    expect(send).toBeEnabled();
    expect(screen.queryByText(/Tick at least one filing/)).not.toBeInTheDocument();
  });

  it("names every checkbox after its filing", async () => {
    loginAs("business");
    fakeApi({
      [`GET ${CA_URL}`]: [200, CA],
      [`GET ${FILINGS_URL}`]: [200, FILINGS],
    });
    renderApp(`/business/marketplace/${CA_ID}/request`);

    const checkbox = await screen.findByRole("checkbox", { name: /GSTR-3B Aug 2026/ });
    expect(checkbox).toHaveAttribute("value", "f1");
    expect(screen.queryByRole("checkbox", { name: "on" })).not.toBeInTheDocument();
  });

  it("shows the API's error, e.g. a filing someone just requested", async () => {
    loginAs("business");
    fakeApi({
      [`GET ${CA_URL}`]: [200, CA],
      [`GET ${FILINGS_URL}`]: [200, FILINGS],
      "POST /api/v1/marketplace/engagements": [
        409,
        {
          error: {
            code: "FILING_ALREADY_REQUESTED",
            message: "Aug 2026 is already requested from a CA or with a CA.",
          },
        },
      ],
    });
    renderApp(`/business/marketplace/${CA_ID}/request`);

    const user = userEvent.setup();
    await user.click(await screen.findByLabelText(/GSTR-3B Aug 2026/));
    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already requested");
  });

  it("asks an unregistered business to register first", async () => {
    loginAs("business");
    fakeApi({
      [`GET ${CA_URL}`]: [200, CA],
      [`GET ${FILINGS_URL}`]: [
        404,
        { error: { code: "BUSINESS_NOT_FOUND", message: "Register your business first." } },
      ],
    });
    renderApp(`/business/marketplace/${CA_ID}/request`);

    expect(await screen.findByRole("link", { name: "Register your business" })).toHaveAttribute(
      "href",
      "/business/onboarding",
    );
  });
});
