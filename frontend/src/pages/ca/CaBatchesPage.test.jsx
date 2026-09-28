import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

beforeEach(() => vi.useFakeTimers({ toFake: ["Date"], now: new Date(2026, 8, 28) }));
afterEach(() => vi.useRealTimers());

describe("deadline batches", () => {
  it("groups filings by form and due date with each client's readiness", async () => {
    loginAs("ca");
    fakeApi({
      "GET /api/v1/ca-workspace/batches": [
        200,
        [
          {
            form_code: "gstr_1",
            due_date: "2026-10-13",
            ready_count: 1,
            filings: [
              {
                business_id: "b1",
                business_name: "Asha Traders",
                compliance_item_id: "f1",
                period_label: "Q2 2026-27",
                status: "with_ca",
                required_total: 4,
                required_ready: 4,
                missing: [],
                ready: true,
              },
              {
                business_id: "b2",
                business_name: "Calm Co",
                compliance_item_id: "f2",
                period_label: "Q2 2026-27",
                status: "with_ca",
                required_total: 4,
                required_ready: 2,
                missing: ["HSN summary", "Customer GSTINs"],
                ready: false,
              },
            ],
          },
        ],
      ],
    });
    renderApp("/ca/batches");

    expect(await screen.findByText("GSTR-1 · due 13 Oct 2026")).toBeInTheDocument();
    expect(screen.getByText(/1 of 2 clients have every required document/)).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(
      screen.getByText("2 of 4 ready · missing: HSN summary, Customer GSTINs"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Calm Co" })).toHaveAttribute("href", "/ca/clients/b2");
  });

  it("is in the CA's sidebar", async () => {
    loginAs("ca");
    fakeApi({ "GET /api/v1/ca-workspace/batches": [200, []] });
    renderApp("/ca/batches");

    expect(await screen.findByText("No filings to do in your active work.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Deadline batches" })).toHaveAttribute(
      "href",
      "/ca/batches",
    );
  });
});
