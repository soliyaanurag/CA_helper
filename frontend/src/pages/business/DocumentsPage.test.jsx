import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const LIST = "/api/v1/documents?page=1&page_size=20";

// "Today" is 28 Sep 2026 (financial year 2026-27).
beforeEach(() => vi.useFakeTimers({ toFake: ["Date"], now: new Date(2026, 8, 28) }));
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function documents(items, total = items.length) {
  return { items, page: 1, page_size: 20, total };
}

const SALES = {
  id: "d1",
  doc_type: "sales_register",
  original_filename: "sales-apr.pdf",
  mime_type: "application/pdf",
  size_bytes: 245_760,
  fy: "2026-27",
  period_label: "Apr 2026",
  ocr_status: "none",
  created_at: "2026-09-20T10:00:00Z",
  links: [
    {
      id: "l1",
      compliance_item_id: "f1",
      form_code: "gstr_1",
      period_label: "Q1 2026-27",
      checklist_key: "sales_invoices",
    },
  ],
  acknowledgement_of: [],
};

const ACK = {
  ...SALES,
  id: "d2",
  doc_type: "acknowledgement",
  original_filename: "ack.pdf",
  size_bytes: 3_500_000,
  period_label: "Q1 2026-27",
  links: [],
  acknowledgement_of: [
    { compliance_item_id: "f2", form_code: "gstr_3b", period_label: "Q1 2026-27" },
  ],
};

function open(answers = {}) {
  loginAs("business");
  const fetchMock = fakeApi({
    [`GET ${LIST}`]: [200, documents([SALES, ACK])],
    "GET /api/v1/compliance/items": [200, []],
    ...answers,
  });
  renderApp("/business/documents");
  return fetchMock;
}

function requested(fetchMock, path, method = "GET") {
  return fetchMock.mock.calls.some(
    ([url, init]) => url === path && (init?.method ?? "GET") === method,
  );
}

describe("document vault", () => {
  it("lists the documents with what they are used for", async () => {
    open();

    const row = (await screen.findByText("sales-apr.pdf")).closest("tr");
    expect(row).toHaveTextContent("Sales register");
    expect(row).toHaveTextContent("2026-27 · Apr 2026");
    expect(row).toHaveTextContent("240 KB");
    expect(within(row).getByRole("link", { name: "GSTR-1 · Q1 2026-27" })).toHaveAttribute(
      "href",
      "/business/compliance/f1",
    );
    const ack = screen.getByText("ack.pdf").closest("tr");
    expect(ack).toHaveTextContent("3.3 MB");
    expect(ack).toHaveTextContent("Acknowledgement of GSTR-3B · Q1 2026-27");
    expect(screen.getByText("2 documents")).toBeInTheDocument();
  });

  it("filters by financial year and type", async () => {
    const fetchMock = open({
      "GET /api/v1/documents?fy=2026-27&page=1&page_size=20": [200, documents([SALES])],
      "GET /api/v1/documents?fy=2026-27&doc_type=acknowledgement&page=1&page_size=20": [
        200,
        documents([ACK]),
      ],
    });
    const user = userEvent.setup();
    await screen.findByText("sales-apr.pdf");

    await user.selectOptions(
      screen.getByLabelText("Financial year", { selector: "#filter_fy" }),
      "2026-27",
    );
    await waitFor(() =>
      expect(requested(fetchMock, "/api/v1/documents?fy=2026-27&page=1&page_size=20")).toBe(true),
    );
    await user.selectOptions(
      screen.getByLabelText("Type", { selector: "#filter_type" }),
      "acknowledgement",
    );

    await waitFor(() => expect(screen.queryByText("sales-apr.pdf")).not.toBeInTheDocument());
    expect(screen.getByText("ack.pdf")).toBeInTheDocument();
  });

  it("uploads a file with its type and year", async () => {
    const fetchMock = open({ "POST /api/v1/documents": [201, SALES] });
    const user = userEvent.setup();
    await screen.findByText("sales-apr.pdf");

    await user.upload(
      screen.getByLabelText("File"),
      new File(["%PDF-1.4"], "sales-apr.pdf", { type: "application/pdf" }),
    );
    await user.selectOptions(
      screen.getByLabelText("Type", { selector: "#upload_type" }),
      "sales_register",
    );
    await user.selectOptions(
      screen.getByLabelText("Financial year", { selector: "#upload_fy" }),
      "2026-27",
    );
    await user.type(screen.getByLabelText("Period (optional)"), "Apr 2026");
    await user.click(screen.getByRole("button", { name: "Upload" }));

    expect(await screen.findByText("Uploaded sales-apr.pdf.")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(
      ([url, init]) => url === "/api/v1/documents" && init?.method === "POST",
    );
    const sent = call[1].body;
    expect(sent.get("doc_type")).toBe("sales_register");
    expect(sent.get("fy")).toBe("2026-27");
    expect(sent.get("period_label")).toBe("Apr 2026");
    expect(sent.get("compliance_item_id")).toBeNull();
  });

  it("asks for a file before uploading", async () => {
    open();
    const user = userEvent.setup();
    await screen.findByText("sales-apr.pdf");

    await user.click(screen.getByRole("button", { name: "Upload" }));

    expect(screen.getByText("Choose a file to upload.")).toBeInTheDocument();
  });

  it("deletes a document after confirming, and explains when it cannot", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const fetchMock = open({
      "DELETE /api/v1/documents/d1": [
        409,
        {
          error: {
            code: "DOCUMENT_IN_USE",
            message: "This document is proof for GSTR-1 (Q1 2026-27), which is filed.",
          },
        },
      ],
      "DELETE /api/v1/documents/d2": [204],
    });
    const user = userEvent.setup();

    const row = (await screen.findByText("sales-apr.pdf")).closest("tr");
    await user.click(within(row).getByRole("button", { name: "Delete" }));
    expect(await within(row).findByRole("alert")).toHaveTextContent("which is filed");

    const ack = screen.getByText("ack.pdf").closest("tr");
    await user.click(within(ack).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(requested(fetchMock, "/api/v1/documents/d2", "DELETE")).toBe(true));
    expect(window.confirm).toHaveBeenCalledWith("Delete ack.pdf?");
  });

  it("does not delete when the confirmation is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const fetchMock = open();
    const user = userEvent.setup();

    const row = (await screen.findByText("sales-apr.pdf")).closest("tr");
    await user.click(within(row).getByRole("button", { name: "Delete" }));

    expect(requested(fetchMock, "/api/v1/documents/d1", "DELETE")).toBe(false);
  });

  it("pages through a long list", async () => {
    const fetchMock = open({
      [`GET ${LIST}`]: [200, documents([SALES], 25)],
      "GET /api/v1/documents?page=2&page_size=20": [200, { ...documents([ACK], 25), page: 2 }],
    });
    const user = userEvent.setup();
    await screen.findByText("Page 1 of 2");

    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("ack.pdf")).toBeInTheDocument();
    expect(screen.getByText("Page 2 of 2")).toBeInTheDocument();
    expect(requested(fetchMock, "/api/v1/documents?page=2&page_size=20")).toBe(true);
  });

  it("says when the vault is empty", async () => {
    open({ [`GET ${LIST}`]: [200, documents([])] });

    expect(await screen.findByText("No documents here yet.")).toBeInTheDocument();
  });
});
