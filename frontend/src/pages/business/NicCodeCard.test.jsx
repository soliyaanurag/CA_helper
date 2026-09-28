import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

// The "Business activity (NIC code)" card on the Business profile page (ON10).

const BUSINESS_URL = "/api/v1/onboarding/business";
const SUGGEST = "POST /api/v1/onboarding/nic-suggestions";
const SAVE = "PUT /api/v1/onboarding/business/nic-code";

const MY_BUSINESS = {
  business: {
    id: "3f1c2b4a-5d6e-4f70-8a9b-0c1d2e3f4a5b",
    legal_name: "Asha Bakery",
    entity_type: "proprietorship",
    state: "Maharashtra",
    annual_turnover: "4500000.00",
  },
  profile: {
    msme_tier: "micro",
    gst_scheme: "not_registered",
    gst_registration_suggested: false,
    itr_form: "itr_4",
    presumptive_eligible: true,
    audit_applicable: false,
    files_24q: false,
    files_26q: false,
    roc_not_tracked: false,
    explanations: {},
  },
  nic_code: null,
};

const BISCUITS = {
  code: "10712",
  description: "Manufacture of biscuits, cakes, pastries, rusks etc.",
};
const BREAD = { code: "10711", description: "Manufacture of bread" };

function routes(extra) {
  return {
    "GET /api/v1/onboarding/states": [200, [{ name: "Maharashtra", code: "27" }]],
    [`GET ${BUSINESS_URL}`]: [200, MY_BUSINESS],
    ...extra,
  };
}

function lastBody(fetchMock, key) {
  let body = null;
  for (const [path, init] of fetchMock.mock.calls) {
    const method = init && init.method ? init.method : "GET";
    if (`${method} ${path}` === key) {
      body = JSON.parse(init.body);
    }
  }
  return body;
}

describe("NIC code card", () => {
  it("says the code is not chosen yet", async () => {
    loginAs("business");
    fakeApi(routes({}));
    renderApp("/business/onboarding");

    expect(await screen.findByText("Business activity (NIC code)")).toBeInTheDocument();
    expect(screen.getByText("Not chosen yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
  });

  it("shows the AI picks and saves the one the user confirms", async () => {
    loginAs("business");
    const fetchMock = fakeApi(
      routes({
        [SUGGEST]: [
          200,
          {
            picks: [
              { ...BISCUITS, reason: "They bake biscuits and cakes.", source: "ai" },
              { ...BREAD, reason: "A bakery may also make bread.", source: "ai" },
            ],
            shortlist: [BISCUITS, BREAD],
            ai_used: true,
          },
        ],
        [SAVE]: [200, BREAD],
      }),
    );
    renderApp("/business/onboarding");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Suggest codes" }));
    expect(await screen.findByText("They bake biscuits and cakes.")).toBeInTheDocument();
    expect(screen.getAllByText("AI suggestion, please check")).toHaveLength(2);
    expect(screen.getByLabelText(/10712/)).toBeChecked(); // the best pick is ticked first

    await user.click(screen.getByLabelText(/10711/));
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(lastBody(fetchMock, SAVE)).toEqual({ code: "10711" });
    expect(screen.getByText(/Your code:/)).toHaveTextContent(
      "Your code: 10711 · Manufacture of bread",
    );
  });

  it("says when the picks are keyword matches only", async () => {
    loginAs("business");
    fakeApi(
      routes({
        [SUGGEST]: [
          200,
          {
            picks: [
              { ...BISCUITS, reason: "Matches words in your description.", source: "keywords" },
            ],
            shortlist: [BISCUITS],
            ai_used: false,
          },
        ],
      }),
    );
    renderApp("/business/onboarding");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Suggest codes" }));

    expect(
      await screen.findByText(
        "AI suggestions are not available right now; these are keyword matches.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Keyword match")).toBeInTheDocument();
  });

  it("finds codes by searching the list", async () => {
    loginAs("business");
    fakeApi(
      routes({
        "GET /api/v1/onboarding/nic-codes?q=bread": [200, [BREAD]],
      }),
    );
    renderApp("/business/onboarding");
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("None of these? Search the list"), "bread");

    expect(await screen.findByLabelText(/10711/)).toBeInTheDocument();
  });

  it("shows the saved code", async () => {
    loginAs("business");
    fakeApi(routes({ [`GET ${BUSINESS_URL}`]: [200, { ...MY_BUSINESS, nic_code: BISCUITS }] }));
    renderApp("/business/onboarding");

    expect(await screen.findByText("10712")).toBeInTheDocument();
    expect(screen.queryByText("Not chosen yet.")).not.toBeInTheDocument();
  });
});
