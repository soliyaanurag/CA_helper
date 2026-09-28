import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { engagement } from "@/test/engagementData";
import { fakeApi, loginAs, renderApp } from "@/test/utils";

const ITEM = "/api/v1/compliance/items/f1";
const FILING_DOCUMENTS = "/api/v1/documents?compliance_item_id=f1&page_size=100";
const VAULT = "/api/v1/documents?page_size=100";

// "Today" is 28 Sep 2026.
beforeEach(() => vi.useFakeTimers({ toFake: ["Date"], now: new Date(2026, 8, 28) }));
afterEach(() => vi.useRealTimers());

// A GET /compliance/items/<id> answer; `filing` and other fields can be changed.
function page({ filing = {}, ...fields } = {}) {
  return {
    filing: {
      id: "f1",
      form_code: "gstr_3b",
      fy: "2026-27",
      period_label: "Q2 2026-27",
      period_start: "2026-07-01",
      period_end: "2026-09-30",
      due_date: "2026-10-22",
      status: "upcoming",
      filing_path: null,
      filed_at: null,
      acknowledgement_no: null,
      ...filing,
    },
    form_name: "GSTR-3B (quarterly, QRMP)",
    content_status: "DRAFT",
    explanation: "# GSTR-3B: what it is\n\nThe summary return.",
    instructions: "# How to file GSTR-3B yourself\n\n1. Log in to the GST portal.\n2. File.",
    checklist: [
      {
        key: "purchase_invoices",
        label: "Purchase invoices",
        required: true,
        help: null,
        ticked: false,
      },
      {
        key: "gstr_2b",
        label: "GSTR-2B statement",
        required: true,
        help: "From the portal",
        ticked: false,
      },
    ],
    acknowledgement: null,
    ...fields,
  };
}

// A GET /documents answer with these documents.
function documents(...items) {
  return { items, page: 1, page_size: 100, total: items.length };
}

// A vault document; `links` are [checklist key] of filing f1.
function vaultFile(id, name, keys = []) {
  return {
    id,
    doc_type: "invoice",
    original_filename: name,
    mime_type: "application/pdf",
    size_bytes: 2048,
    fy: "2026-27",
    period_label: "Q2 2026-27",
    ocr_status: "none",
    created_at: "2026-09-20T10:00:00Z",
    links: keys.map((key) => ({
      id: "link-" + id + "-" + key,
      compliance_item_id: "f1",
      form_code: "gstr_3b",
      period_label: "Q2 2026-27",
      checklist_key: key,
    })),
    acknowledgement_of: [],
  };
}

function open(answers = {}) {
  loginAs("business");
  const fetchMock = fakeApi({
    [`GET ${ITEM}`]: [200, page()],
    "GET /api/v1/marketplace/my-engagements": [200, []],
    [`GET ${FILING_DOCUMENTS}`]: [200, documents()],
    ...answers,
  });
  renderApp("/business/compliance/f1");
  return fetchMock;
}

function sentBody(fetchMock, path) {
  const call = fetchMock.mock.calls.find(([url, init]) => url === path && init?.method === "POST");
  return call[1].body;
}

describe("filing page", () => {
  it("shows the filing, the steps to file it and that the guide is a draft", async () => {
    open();

    expect(
      await screen.findByRole("heading", { name: /GSTR-3B · Q2 2026-27/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/due 22 Oct 2026 · In 24 days/)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "How to file GSTR-3B yourself" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/This guide is a draft/)).toBeInTheDocument();

    await userEvent.setup().click(screen.getByRole("tab", { name: "What is this form?" }));
    expect(screen.getByText("The summary return.")).toBeInTheDocument();
  });

  it("chooses to file it myself, then marks it filed with the ARN", async () => {
    const fetchMock = open({
      [`POST ${ITEM}/path`]: [200, page({ filing: { filing_path: "self" } })],
      [`POST ${ITEM}/mark-filed`]: [
        200,
        page({
          filing: {
            filing_path: "self",
            status: "filed",
            filed_at: "2026-09-28T06:00:00Z",
            acknowledgement_no: "AA270926123456X",
          },
        }),
      ],
    });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "I'll file it myself" }));
    expect(JSON.parse(sentBody(fetchMock, `${ITEM}/path`))).toEqual({ path: "self" });

    await user.type(await screen.findByLabelText(/Acknowledgement number/), "AA270926123456X");
    await user.click(screen.getByRole("button", { name: "Mark as filed" }));

    expect(await screen.findByText(/Acknowledgement number: AA270926123456X/)).toBeInTheDocument();
    expect(sentBody(fetchMock, `${ITEM}/mark-filed`).get("acknowledgement_no")).toBe(
      "AA270926123456X",
    );
    expect(screen.getByRole("button", { name: "Undo: not filed yet" })).toBeInTheDocument();
  });

  it("ticks a document and shows the new status", async () => {
    const ticked = page({ filing: { status: "docs_pending" } });
    ticked.checklist[0].ticked = true;
    const fetchMock = open({ [`POST ${ITEM}/checklist`]: [200, ticked] });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("checkbox", { name: /Purchase invoices/ }));

    expect(
      await screen.findByText("1 of 2 required documents ready.", { exact: false }),
    ).toBeInTheDocument();
    expect(screen.getByText("Docs pending")).toBeInTheDocument();
    expect(JSON.parse(sentBody(fetchMock, `${ITEM}/checklist`))).toEqual({
      key: "purchase_invoices",
      ticked: true,
    });
  });

  it("links to the marketplace for this form after choosing a CA", async () => {
    open({ [`GET ${ITEM}`]: [200, page({ filing: { filing_path: "ca" } })] });

    expect(await screen.findByRole("link", { name: /Find a CA for this filing/ })).toHaveAttribute(
      "href",
      "/business/marketplace?service=gstr_3b",
    );
  });

  it("names the CA when the filing is in an active engagement", async () => {
    open({
      [`GET ${ITEM}`]: [200, page({ filing: { status: "with_ca", filing_path: "ca" } })],
      "GET /api/v1/marketplace/my-engagements": [200, [engagement({ status: "active" })]],
    });

    await waitFor(() =>
      expect(screen.getByText(/Meera Shah is working on this filing/)).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: "I'll file it myself" })).not.toBeInTheDocument();
  });

  it("is opened from the compliance calendar", async () => {
    loginAs("business");
    fakeApi({ "GET /api/v1/compliance/items": [200, [page().filing]] });
    renderApp("/business/compliance");

    expect(await screen.findByRole("link", { name: "GSTR-3B" })).toHaveAttribute(
      "href",
      "/business/compliance/f1",
    );
  });
});

describe("late fees on the filing page", () => {
  // A GET /alerts/penalties/<id> answer while the rules have no confirmed amount.
  const PENDING = {
    compliance_item_id: "f1",
    form_code: "gstr_3b",
    period_label: "Q1 2026-27",
    due_date: "2026-07-22",
    days_late: 68,
    status: "pending",
    late_fee: null,
    interest: null,
    total: null,
    notes: ["The late fee for this form is not confirmed yet."],
    label: "Estimate (rules pending verification)",
  };
  const LATE = page({ filing: { due_date: "2026-07-22", status: "overdue" } });

  it("shows an estimate for an overdue filing, labelled as unverified", async () => {
    open({
      [`GET ${ITEM}`]: [200, LATE],
      "GET /api/v1/alerts/penalties/f1": [200, PENDING],
    });

    const card = (await screen.findByText("Late fees and interest")).closest("[data-slot=card]");
    expect(card).toHaveTextContent("Estimate (rules pending verification)");
    await waitFor(() => expect(card).toHaveTextContent("68 days late."));
    expect(card).toHaveTextContent("Late fee: not available");
    expect(card).toHaveTextContent("The late fee for this form is not confirmed yet.");
  });

  it("adds the interest for the tax due", async () => {
    const fetchMock = open({
      [`GET ${ITEM}`]: [200, LATE],
      "GET /api/v1/alerts/penalties/f1": [200, PENDING],
      "GET /api/v1/alerts/penalties/f1?tax_due=36500": [
        200,
        { ...PENDING, status: "estimated", interest: "816.00", total: "816.00", notes: [] },
      ],
    });
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText(/Tax due/), "36500");
    await user.click(screen.getByRole("button", { name: "Estimate" }));

    expect(await screen.findByText("Total: ₹816")).toBeInTheDocument();
    expect(screen.getByText("Interest: ₹816")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([url]) => url === "/api/v1/alerts/penalties/f1?tax_due=36500"),
    ).toBe(true);
  });

  it("shows no penalty card before the due date", async () => {
    const fetchMock = open();

    await screen.findByRole("heading", { name: /GSTR-3B · Q2 2026-27/ });
    expect(screen.queryByText("Late fees and interest")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url.startsWith("/api/v1/alerts/penalties"))).toBe(
      false,
    );
  });
});

describe("filing page documents", () => {
  it("shows the files linked to each entry and to the filing", async () => {
    open({
      [`GET ${FILING_DOCUMENTS}`]: [
        200,
        documents(
          vaultFile("d1", "invoices-q2.pdf", ["purchase_invoices"]),
          vaultFile("d2", "notes.pdf", ["general"]),
        ),
      ],
    });

    expect(await screen.findByText("invoices-q2.pdf")).toBeInTheDocument();
    expect(screen.getByText("notes.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove invoices-q2.pdf" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add a file for GSTR-2B statement" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add a file for this filing" })).toBeInTheDocument();
  });

  it("keeps the files of a filed filing fixed", async () => {
    open({
      [`GET ${ITEM}`]: [
        200,
        page({ filing: { status: "filed", filed_at: "2026-09-20T10:00:00Z" } }),
      ],
      [`GET ${FILING_DOCUMENTS}`]: [
        200,
        documents(vaultFile("d1", "invoices-q2.pdf", ["purchase_invoices"])),
      ],
    });

    expect(await screen.findByRole("button", { name: "Open invoices-q2.pdf" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Add a file/ })).not.toBeInTheDocument();
  });

  it("uploads a file for a checklist entry", async () => {
    const fetchMock = open({
      [`GET ${VAULT}`]: [200, documents()],
      "POST /api/v1/documents": [201, vaultFile("d3", "2b.pdf", ["gstr_2b"])],
    });
    const user = userEvent.setup();

    await user.click(
      await screen.findByRole("button", { name: "Add a file for GSTR-2B statement" }),
    );
    await user.upload(
      screen.getByLabelText("Upload a new file"),
      new File(["%PDF-1.4"], "2b.pdf", { type: "application/pdf" }),
    );
    await user.selectOptions(screen.getByLabelText("Type"), "invoice");
    await user.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() =>
      expect(screen.queryByLabelText("Upload a new file")).not.toBeInTheDocument(),
    );
    const sent = sentBody(fetchMock, "/api/v1/documents");
    expect(sent.get("file").name).toBe("2b.pdf");
    expect(sent.get("doc_type")).toBe("invoice");
    expect(sent.get("compliance_item_id")).toBe("f1");
    expect(sent.get("checklist_key")).toBe("gstr_2b");
  });

  it("links a file from the vault", async () => {
    const fetchMock = open({
      [`GET ${VAULT}`]: [200, documents(vaultFile("d4", "bank.pdf"))],
      "POST /api/v1/documents/d4/links": [200, vaultFile("d4", "bank.pdf", ["general"])],
    });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Add a file for this filing" }));
    await user.selectOptions(
      await screen.findByLabelText("Or link one from your vault"),
      "bank.pdf (Invoice)",
    );
    await user.click(screen.getByRole("button", { name: "Link" }));

    await waitFor(() =>
      expect(JSON.parse(sentBody(fetchMock, "/api/v1/documents/d4/links"))).toEqual({
        compliance_item_id: "f1",
        checklist_key: "general",
      }),
    );
  });

  it("removes a linked file and shows why it failed", async () => {
    const fetchMock = open({
      [`GET ${FILING_DOCUMENTS}`]: [
        200,
        documents(vaultFile("d1", "invoices-q2.pdf", ["purchase_invoices"])),
      ],
      "DELETE /api/v1/documents/links/link-d1-purchase_invoices": [
        409,
        { error: { code: "FILING_LOCKED", message: "This filing is filed." } },
      ],
    });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Remove invoices-q2.pdf" }));

    expect(await screen.findByText("This filing is filed.")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          url === "/api/v1/documents/links/link-d1-purchase_invoices" && init.method === "DELETE",
      ),
    ).toBe(true);
  });
});

describe("documents the CA asked for", () => {
  const REQUESTS = "/api/v1/ca-workspace/document-requests?compliance_item_id=f1";
  const REQUEST = {
    id: "r1",
    compliance_item_id: "f1",
    form_code: "gstr_3b",
    period_label: "Q2 2026-27",
    checklist_key: "gstr_2b",
    message: "The 2B for the quarter",
    status: "open",
    created_at: "2026-09-25T10:00:00Z",
    fulfilled_at: null,
    document_id: null,
    ca_name: "Meera Shah",
  };

  it("sends a vault file for the request", async () => {
    const fetchMock = open({
      [`GET ${REQUESTS}`]: [200, [REQUEST]],
      [`GET ${VAULT}`]: [200, documents(vaultFile("d7", "2b-q2.pdf"))],
      "POST /api/v1/ca-workspace/document-requests/r1/fulfil": [
        200,
        { ...REQUEST, status: "fulfilled" },
      ],
    });
    const user = userEvent.setup();

    expect(await screen.findByText("Your CA asked for documents")).toBeInTheDocument();
    expect(screen.getByText(/Meera Shah: “The 2B for the quarter”/)).toBeInTheDocument();
    await user.selectOptions(
      await screen.findByLabelText("or choose from your vault"),
      "2b-q2.pdf",
    );
    await user.click(screen.getByRole("button", { name: "Send to my CA" }));

    await waitFor(() =>
      expect(
        JSON.parse(sentBody(fetchMock, "/api/v1/ca-workspace/document-requests/r1/fulfil")),
      ).toEqual({ document_id: "d7" }),
    );
  });

  it("uploads a new file, then sends it", async () => {
    const fetchMock = open({
      [`GET ${REQUESTS}`]: [200, [REQUEST]],
      [`GET ${VAULT}`]: [200, documents()],
      "POST /api/v1/documents": [201, vaultFile("d8", "2b.pdf")],
      "POST /api/v1/ca-workspace/document-requests/r1/fulfil": [
        200,
        { ...REQUEST, status: "fulfilled" },
      ],
    });
    const user = userEvent.setup();

    await user.upload(
      await screen.findByLabelText("Upload a file"),
      new File(["%PDF-1.4"], "2b.pdf", { type: "application/pdf" }),
    );
    await user.click(screen.getByRole("button", { name: "Send to my CA" }));

    await waitFor(() =>
      expect(
        JSON.parse(sentBody(fetchMock, "/api/v1/ca-workspace/document-requests/r1/fulfil")),
      ).toEqual({ document_id: "d8" }),
    );
    expect(sentBody(fetchMock, "/api/v1/documents").get("file").name).toBe("2b.pdf");
  });

  it("shows nothing when the CA asked for nothing", async () => {
    open({ [`GET ${REQUESTS}`]: [200, []] });

    await screen.findByRole("heading", { name: /GSTR-3B · Q2 2026-27/ });
    expect(screen.queryByText("Your CA asked for documents")).not.toBeInTheDocument();
  });
});

describe("how similar businesses file it", () => {
  const PEERS = "/api/v1/compliance/items/f1/peer-insights";
  const figures = {
    form_code: "gstr_3b",
    scope: "segment",
    entity_type: "proprietorship",
    msme_tier: "micro",
    min_businesses: 10,
    business_count: 10,
    filing_count: 40,
    self: { count: 24, share_pct: 60, on_time_pct: 88 },
    ca: { count: 16, share_pct: 40, on_time_pct: 100 },
  };

  it("shows the segment's figures", async () => {
    open({ [`GET ${PEERS}`]: [200, figures] });

    const card = (await screen.findByText("How similar businesses file it")).closest(
      "[data-slot=card]",
    );
    expect(card).toHaveTextContent(
      "Among 10 micro businesses like yours (proprietorship) that filed GSTR-3B:",
    );
    expect(card).toHaveTextContent("Filed it themselves60%88% of them on time");
    expect(card).toHaveTextContent("Filed it through a CA40%100% of them on time");
  });

  it("falls back to every business, or says there are too few", async () => {
    open({ [`GET ${PEERS}`]: [200, { ...figures, scope: "overall", business_count: 12 }] });
    expect(
      await screen.findByText("Among all 12 businesses on CA Helper that filed GSTR-3B:"),
    ).toBeInTheDocument();
  });

  it("says when too few businesses filed it", async () => {
    open({
      [`GET ${PEERS}`]: [200, { ...figures, scope: "none", self: null, ca: null }],
    });
    expect(
      await screen.findByText(/Not enough businesses have filed GSTR-3B here yet/),
    ).toBeInTheDocument();
  });
});

describe("acknowledgement verification (DO8)", () => {
  function filedPage(status, verification) {
    return page({
      filing: {
        status,
        filing_path: "self",
        filed_at: "2026-10-20T06:00:00Z",
        acknowledgement_no: "AA2710260123456",
      },
      acknowledgement: { filename: "ack.pdf", uploaded_at: "2026-10-20T06:00:00Z", verification },
    });
  }

  it("shows a verified filing", async () => {
    open({
      [`GET ${ITEM}`]: [
        200,
        filedPage("filed_verified", {
          verified: true,
          problems: [],
          acknowledgement_no: "AA2710260123456",
          filing_date: "2026-10-20",
        }),
      ],
      [`GET ${ITEM}/acknowledgement`]: [200, {}],
    });

    expect(await screen.findByText("Filed and verified")).toBeInTheDocument();
    expect(
      screen.getByText(/Verified from the acknowledgement: number AA2710260123456/),
    ).toBeInTheDocument();
  });

  it("says what did not match", async () => {
    open({
      [`GET ${ITEM}`]: [
        200,
        filedPage("filed", {
          verified: false,
          problems: ["It does not name the form GSTR-3B."],
          acknowledgement_no: null,
          filing_date: null,
        }),
      ],
      [`GET ${ITEM}/acknowledgement`]: [200, {}],
    });

    expect(await screen.findByText(/We could not verify it/)).toBeInTheDocument();
    expect(screen.getByText("It does not name the form GSTR-3B.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Undo: not filed yet" })).toBeInTheDocument();
  });
});
