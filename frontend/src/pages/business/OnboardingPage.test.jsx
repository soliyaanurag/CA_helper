import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const URL = "/api/v1/onboarding/business";
const STATES = [
  { name: "Gujarat", code: "24" },
  { name: "Maharashtra", code: "27" },
];
const STATES_ROUTE = { "GET /api/v1/onboarding/states": [200, STATES] };
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
  await user.selectOptions(screen.getByLabelText("State"), "Maharashtra");
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
    fakeApi({ ...STATES_ROUTE, [`GET ${URL}`]: NOT_FOUND });
    renderApp("/business/onboarding");

    expect(await screen.findByText("Register your business")).toBeInTheDocument();
    expect(screen.queryByLabelText("GSTIN")).not.toBeInTheDocument();
  });

  it("asks for the GSTIN only when GST registered", async () => {
    loginAs("business");
    fakeApi({ ...STATES_ROUTE, [`GET ${URL}`]: NOT_FOUND });
    renderApp("/business/onboarding");
    const user = userEvent.setup();

    await user.click(await screen.findByLabelText("GST registered"));
    await user.click(screen.getByRole("button", { name: "Register business" }));

    expect(await screen.findByText("Enter a valid 15-character GSTIN.")).toBeInTheDocument();
  });

  it("registers and then shows the profile with the reasons", async () => {
    loginAs("business");
    const fetchMock = fakeApi({
      ...STATES_ROUTE,
      [`GET ${URL}`]: NOT_FOUND,
      [`POST ${URL}`]: [201, SAVED],
    });
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
    fakeApi({ ...STATES_ROUTE, [`GET ${URL}`]: [200, SAVED] });
    renderApp("/business/onboarding");

    expect(await screen.findByText("Asha Traders")).toBeInTheDocument();
    // The MSME tier line of the profile (the summary chips repeat it).
    expect(screen.getByText("MSME tier").parentElement).toHaveTextContent("Micro");
    expect(screen.getByRole("link", { name: "compliance calendar" })).toHaveAttribute(
      "href",
      "/business/compliance",
    );
  });

  it("checks the GSTIN's check character, state code and PAN before sending", async () => {
    loginAs("business");
    const fetchMock = fakeApi({ ...STATES_ROUTE, [`GET ${URL}`]: NOT_FOUND });
    renderApp("/business/onboarding");
    await screen.findByText("Register your business");

    const user = await fillForm();
    await user.click(screen.getByLabelText("GST registered"));
    await user.type(screen.getByLabelText("GSTIN"), "24ABCDE1234F1Z6"); // valid, but Gujarat's
    await user.click(screen.getByRole("button", { name: "Register business" }));

    expect(await screen.findByText(/the code of Maharashtra is 27/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("sends the QRMP choice", async () => {
    loginAs("business");
    const fetchMock = fakeApi({
      ...STATES_ROUTE,
      [`GET ${URL}`]: NOT_FOUND,
      [`POST ${URL}`]: [201, SAVED],
    });
    renderApp("/business/onboarding");
    await screen.findByText("Register your business");

    const user = await fillForm();
    await user.click(screen.getByLabelText("GST registered"));
    await user.type(screen.getByLabelText("GSTIN"), "27ABCDE1234F1Z0");
    await user.click(screen.getByLabelText("Quarterly (QRMP)"));
    await user.click(screen.getByRole("button", { name: "Register business" }));

    await screen.findByText("Your regulatory profile");
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === "POST");
    expect(JSON.parse(init.body)).toMatchObject({ gst_qrmp: true, gstin: "27ABCDE1234F1Z0" });
  });

  it("asks partnerships and LLPs about an audit under another law", async () => {
    loginAs("business");
    fakeApi({ ...STATES_ROUTE, [`GET ${URL}`]: NOT_FOUND });
    renderApp("/business/onboarding");
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("Type of business"), "proprietorship");
    expect(screen.queryByLabelText(/audited under another law/)).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Type of business"), "llp");
    expect(screen.getByLabelText(/audited under another law/)).toBeInTheDocument();
  });

  it("edits the details and shows what changed", async () => {
    loginAs("business");
    const business = {
      ...SAVED.business,
      address: "Pune",
      description: "Retail shop",
      investment_amount: "800000.00",
      pan: "ABCDE1234F",
      phone: "9876543210",
      gst_registered: true,
      gstin: "27ABCDE1234F1Z0",
      gst_composition: false,
      gst_qrmp: true,
      accounts_audited_other_law: false,
      deducts_tds: false,
      tan: null,
      pays_salary_above_limit: false,
      cin_llpin: null,
      udyam_number: null,
      state_needs_review: false,
    };
    const updated = {
      business: { ...business, gst_qrmp: false },
      profile: { ...SAVED.profile, gst_scheme: "regular_monthly" },
      changes: {
        profile: [{ line: "gst_scheme", old: "regular_qrmp", new: "regular_monthly" }],
        filings: { added: 16, removed: 0, kept_with_ca: 0 },
      },
    };
    const fetchMock = fakeApi({
      ...STATES_ROUTE,
      [`GET ${URL}`]: [200, { ...SAVED, business }],
      [`PUT ${URL}`]: [200, updated],
    });
    renderApp("/business/onboarding");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Edit details" }));
    expect(screen.getByLabelText("State")).toHaveValue("Maharashtra");
    await user.click(screen.getByLabelText("Monthly"));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    const summary = await screen.findByRole("status");
    expect(summary).toHaveTextContent("GST scheme: Regular (quarterly, QRMP) → Regular (monthly)");
    expect(summary).toHaveTextContent("16 filings added");
    const [, init] = fetchMock.mock.calls.find(([, options]) => options?.method === "PUT");
    const sent = JSON.parse(init.body);
    expect(sent.gst_qrmp).toBe(false);
    expect(sent).not.toHaveProperty("id"); // only the form's own fields
  });

  it("shows the profile summary chips", async () => {
    loginAs("business");
    fakeApi({ ...STATES_ROUTE, [`GET ${URL}`]: [200, SAVED] });
    renderApp("/business/onboarding");

    const chips = await screen.findByRole("list", { name: "Profile summary" });
    expect(chips).toHaveTextContent("Micro");
    expect(chips).toHaveTextContent("QRMP");
    expect(chips).toHaveTextContent("ITR-4");
  });
});

describe("fill in from a document (ON13)", () => {
  it("puts the values found in a GST certificate into the form", async () => {
    loginAs("business");
    const fetchMock = fakeApi({
      ...STATES_ROUTE,
      [`GET ${URL}`]: NOT_FOUND,
      "POST /api/v1/onboarding/autofill": [
        200,
        {
          found: {
            gstin: "27ABCDE1234F1Z5",
            pan: "ABCDE1234F",
            state: "Maharashtra",
            legal_name: "ASHA TRADERS PRIVATE LIMITED",
            entity_type: "private_limited",
          },
        },
      ],
    });
    renderApp("/business/onboarding");
    const user = userEvent.setup();
    const certificate = new File(["%PDF-1.4"], "certificate.pdf", { type: "application/pdf" });

    await user.upload(
      await screen.findByLabelText(/Fill in from your GST certificate/),
      certificate,
    );

    expect(
      await screen.findByText(/Filled in: business name, type of business/),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Business name")).toHaveValue("ASHA TRADERS PRIVATE LIMITED");
    expect(screen.getByLabelText("PAN")).toHaveValue("ABCDE1234F");
    expect(screen.getByLabelText("State")).toHaveValue("Maharashtra");
    expect(screen.getByLabelText("GST registered")).toBeChecked();
    expect(screen.getByLabelText("GSTIN")).toHaveValue("27ABCDE1234F1Z5");
    const call = fetchMock.mock.calls.find(([path]) => path === "/api/v1/onboarding/autofill");
    expect(call[1].body.get("file").name).toBe("certificate.pdf");
  });

  it("says when a file cannot be read", async () => {
    loginAs("business");
    fakeApi({
      ...STATES_ROUTE,
      [`GET ${URL}`]: NOT_FOUND,
      "POST /api/v1/onboarding/autofill": [
        422,
        { error: { code: "DOCUMENT_UNREADABLE", message: "We could not read this file." } },
      ],
    });
    renderApp("/business/onboarding");
    const user = userEvent.setup();
    const photo = new File(["x"], "blurry.png", { type: "image/png" });

    await user.upload(await screen.findByLabelText(/Fill in from your GST certificate/), photo);

    expect(await screen.findByRole("alert")).toHaveTextContent("We could not read this file.");
  });
});
