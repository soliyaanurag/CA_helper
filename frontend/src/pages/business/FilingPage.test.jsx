import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { engagement } from "@/test/engagementData";
import { fakeApi, loginAs, renderApp } from "@/test/utils";

const ITEM = "/api/v1/compliance/items/f1";

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

function open(answers = {}) {
  loginAs("business");
  const fetchMock = fakeApi({
    [`GET ${ITEM}`]: [200, page()],
    "GET /api/v1/marketplace/my-engagements": [200, []],
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

    await user.click(await screen.findByLabelText(/Purchase invoices/));

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
