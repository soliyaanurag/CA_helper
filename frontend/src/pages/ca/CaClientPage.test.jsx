import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const CLIENT = "/api/v1/ca-workspace/clients/b1";

beforeEach(() => vi.useFakeTimers({ toFake: ["Date"], now: new Date(2026, 8, 28) }));
afterEach(() => vi.useRealTimers());

function filingRow({ status = "with_ca", ...fields } = {}) {
  return {
    filing: {
      id: "f1",
      form_code: "gstr_1",
      fy: "2026-27",
      period_label: "Q2 2026-27",
      period_start: "2026-07-01",
      period_end: "2026-09-30",
      due_date: "2026-10-13",
      status,
      filing_path: "ca",
      filed_at: null,
      acknowledgement_no: null,
    },
    checklist: [
      { key: "sales_invoices", label: "Sales invoices", required: true, help: null, ticked: true },
      { key: "hsn_summary", label: "HSN summary", required: true, help: null, ticked: false },
    ],
    documents: [
      {
        document_id: "d1",
        original_filename: "invoices.pdf",
        doc_type: "invoice",
        size_bytes: 2048,
        created_at: "2026-09-20T10:00:00Z",
        checklist_key: "sales_invoices",
      },
    ],
    open_requests: [
      {
        id: "r1",
        compliance_item_id: "f1",
        form_code: "gstr_1",
        period_label: "Q2 2026-27",
        checklist_key: "hsn_summary",
        message: "The HSN summary please",
        status: "open",
        created_at: "2026-09-25T10:00:00Z",
        fulfilled_at: null,
        document_id: null,
      },
    ],
    ...fields,
  };
}

const WORKSPACE = {
  business: {
    id: "b1",
    legal_name: "Asha Traders",
    entity_type: "proprietorship",
    state: "Maharashtra",
    address: "Pune",
    description: "Retail shop",
    annual_turnover: "4500000.00",
    investment_amount: "800000.00",
    pan: "ABCDE1234F",
    phone: "9876543210",
    gst_registered: true,
    gstin: "27ABCDE1234F1Z5",
    gst_composition: false,
    gst_qrmp: true,
    accounts_audited_other_law: false,
    deducts_tds: false,
    tan: null,
    pays_salary_above_limit: false,
    cin_llpin: null,
    udyam_number: null,
    state_needs_review: false,
  },
  profile: {
    msme_tier: "micro",
    gst_scheme: "regular_qrmp",
    itr_form: "itr_3",
    audit_applicable: false,
  },
  filings: [filingRow()],
};

function open(answers = {}) {
  loginAs("ca");
  const fetchMock = fakeApi({ [`GET ${CLIENT}`]: [200, WORKSPACE], ...answers });
  renderApp("/ca/clients/b1");
  return fetchMock;
}

function sent(fetchMock, path) {
  return fetchMock.mock.calls.find(([url, init]) => url === path && init?.method === "POST")[1]
    .body;
}

describe("client workspace", () => {
  it("shows the profile and each engaged filing with its documents and requests", async () => {
    open();

    expect(await screen.findByRole("heading", { name: "Asha Traders" })).toBeInTheDocument();
    expect(screen.getByText("ABCDE1234F")).toBeInTheDocument();
    expect(screen.getByText("Regular (quarterly, QRMP)")).toBeInTheDocument();
    expect(screen.getByText(/GSTR-1 · Q2 2026-27/)).toBeInTheDocument();
    expect(screen.getByText("Documents: 1 of 2 required ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open invoices.pdf" })).toBeInTheDocument();
    expect(screen.getByText("HSN summary: The HSN summary please")).toBeInTheDocument();
  });

  it("asks the client for a document", async () => {
    const fetchMock = open({
      "POST /api/v1/ca-workspace/clients/b1/document-requests": [201, {}],
    });
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Message"), "Send the HSN summary");
    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(await screen.findByText(/The client sees it as a to-do/)).toBeInTheDocument();
    expect(
      JSON.parse(sent(fetchMock, "/api/v1/ca-workspace/clients/b1/document-requests")),
    ).toEqual({
      compliance_item_id: "f1",
      checklist_key: "hsn_summary", // the first entry not ticked yet
      message: "Send the HSN summary",
    });
  });

  it("cancels a request", async () => {
    const fetchMock = open({ "POST /api/v1/ca-workspace/document-requests/r1/cancel": [200, {}] });

    await userEvent.setup().click(await screen.findByRole("button", { name: "Cancel request" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url]) => url === "/api/v1/ca-workspace/document-requests/r1/cancel",
        ),
      ).toBe(true),
    );
  });

  it("marks the filing filed and says when the engagement is completed", async () => {
    const fetchMock = open({
      "POST /api/v1/ca-workspace/clients/b1/filings/f1/mark-filed": [
        200,
        {
          compliance_item_id: "f1",
          status: "filed",
          acknowledgement_no: "AA27",
          engagement_completed: true,
        },
      ],
    });
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText(/Acknowledgement number/), "AA27");
    await user.upload(
      screen.getByLabelText(/Acknowledgement file/),
      new File(["%PDF-1.4"], "ack.pdf", { type: "application/pdf" }),
    );
    await user.click(screen.getByRole("button", { name: "Mark as filed" }));

    expect(await screen.findByText(/it is now completed/)).toBeInTheDocument();
    const body = sent(fetchMock, "/api/v1/ca-workspace/clients/b1/filings/f1/mark-filed");
    expect(body.get("acknowledgement_no")).toBe("AA27");
    expect(body.get("file").name).toBe("ack.pdf");
  });

  it("offers no actions on a filed filing", async () => {
    open({
      [`GET ${CLIENT}`]: [
        200,
        { ...WORKSPACE, filings: [filingRow({ status: "filed", open_requests: [] })] },
      ],
    });

    await screen.findByRole("heading", { name: "Asha Traders" });
    expect(screen.queryByRole("button", { name: "Send request" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark as filed" })).not.toBeInTheDocument();
  });

  it("says when the business is not an active client", async () => {
    open({
      [`GET ${CLIENT}`]: [
        404,
        { error: { code: "BUSINESS_NOT_FOUND", message: "This business was not found." } },
      ],
    });

    expect(await screen.findByText("This business was not found.")).toBeInTheDocument();
  });
});
