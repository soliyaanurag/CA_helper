import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const URL = "/api/v1/onboarding/business";
const NOT_FOUND = [404, { error: { code: "BUSINESS_NOT_FOUND", message: "Register first." } }];

const SAVED = {
  business: {
    id: "3f1c2b4a-5d6e-4f70-8a9b-0c1d2e3f4a5b",
    legal_name: "Asha Traders",
    entity_type: "proprietorship",
    state: "Maharashtra",
    annual_turnover: "4500000.00",
  },
  profile: {
    msme_tier: "micro",
    gst_scheme: "regular_qrmp",
    gst_registration_suggested: false,
    itr_form: "itr_4",
    presumptive_eligible: true,
    audit_applicable: false,
    files_24q: false,
    files_26q: false,
    roc_not_tracked: false,
    explanations: {
      msme_tier: "Investment is within the micro limits.",
      gst_scheme: "Turnover is within ₹50,000,000, so returns are quarterly (QRMP).",
      itr_form: "Presumptive income is filed in ITR-4.",
      presumptive_eligible: "Turnover is within ₹20,000,000.",
      audit_applicable: "No tax audit when you use the presumptive scheme.",
      files_24q: "You do not deduct TDS on salaries.",
      files_26q: "You do not deduct TDS.",
      roc_not_tracked: "No ROC/MCA filings for this business type.",
    },
  },
};

async function fillForm() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Business name"), "Asha Traders");
  await user.selectOptions(screen.getByLabelText("Type of business"), "proprietorship");
  await user.type(screen.getByLabelText("State"), "Maharashtra");
  await user.type(screen.getByLabelText("Mobile number"), "9876543210");
  await user.type(screen.getByLabelText("Annual turnover (₹)"), "4500000");
  await user.type(screen.getByLabelText("Investment in plant & machinery (₹)"), "800000");
  await user.type(screen.getByLabelText("PAN"), "abcde1234f");
  await user.type(screen.getByLabelText("Address"), "Pune");
  await user.type(screen.getByLabelText("What does the business do?"), "Retail shop");
  return user;
}

describe("business profile page", () => {
  it("shows the registration form before the business is registered", async () => {
    loginAs("business");
    fakeApi({ [`GET ${URL}`]: NOT_FOUND });
    renderApp("/business/onboarding");

    expect(await screen.findByText("Register your business")).toBeInTheDocument();
    expect(screen.queryByLabelText("GSTIN")).not.toBeInTheDocument();
  });

  it("asks for the GSTIN only when GST registered", async () => {
    loginAs("business");
    fakeApi({ [`GET ${URL}`]: NOT_FOUND });
    renderApp("/business/onboarding");
    const user = userEvent.setup();

    await user.click(await screen.findByLabelText("GST registered"));
    await user.click(screen.getByRole("button", { name: "Register business" }));

    expect(await screen.findByText("Enter a valid 15-character GSTIN.")).toBeInTheDocument();
  });

  it("registers and then shows the profile with the reasons", async () => {
    loginAs("business");
    const fetchMock = fakeApi({ [`GET ${URL}`]: NOT_FOUND, [`POST ${URL}`]: [201, SAVED] });
    renderApp("/business/onboarding");
    await screen.findByText("Register your business");

    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: "Register business" }));

    expect(await screen.findByText("Your regulatory profile")).toBeInTheDocument();
    expect(screen.getByText("Regular (quarterly, QRMP)")).toBeInTheDocument();
    expect(screen.getByText("Presumptive income is filed in ITR-4.")).toBeInTheDocument();
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === "POST");
    const sent = JSON.parse(init.body);
    expect(sent.pan).toBe("ABCDE1234F"); // capitalised
    expect(sent.gstin).toBeNull(); // not GST registered
  });

  it("shows the saved profile", async () => {
    loginAs("business");
    fakeApi({ [`GET ${URL}`]: [200, SAVED] });
    renderApp("/business/onboarding");

    expect(await screen.findByText("Asha Traders")).toBeInTheDocument();
    expect(screen.getByText("Micro")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "compliance calendar" })).toHaveAttribute(
      "href",
      "/business/compliance",
    );
  });
});
