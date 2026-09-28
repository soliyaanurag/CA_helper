import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

// "Today" is 28 Sep 2026.
beforeEach(() => vi.useFakeTimers({ toFake: ["Date"], now: new Date(2026, 8, 28) }));
afterEach(() => vi.useRealTimers());

const URGENT = {
  business_id: "b1",
  business_name: "Asha Traders",
  filing_count: 2,
  open_filing_count: 2,
  open_request_count: 1,
  next_deadline: "2026-10-13",
  overdue_count: 1,
  missing_documents: 8,
  score: 83,
  reasons: [
    { reason: "1 filing(s) overdue", points: 40 },
    { reason: "8 required document(s) not ready", points: 40 },
    { reason: "1 document request(s) not answered", points: 3 },
  ],
};
const CALM = {
  ...URGENT,
  business_id: "b2",
  business_name: "Calm Co",
  overdue_count: 0,
  open_request_count: 0,
  next_deadline: null,
  score: 0,
  reasons: [],
};

function open(clients) {
  loginAs("ca");
  fakeApi({ "GET /api/v1/ca-workspace/clients": [200, clients] });
  renderApp("/ca/clients");
}

describe("my clients", () => {
  it("lists clients by urgency with why each is flagged", async () => {
    open([URGENT, CALM]);

    const link = await screen.findByRole("link", { name: "Asha Traders" });
    expect(link).toHaveAttribute("href", "/ca/clients/b1");
    expect(screen.getByText("Urgency 83")).toBeInTheDocument();
    expect(screen.getByText("1 filing(s) overdue")).toBeInTheDocument();
    expect(screen.getByText(/next deadline 13 Oct 2026 \(in 15 days\)/)).toBeInTheDocument();
    expect(screen.getByText("Urgency 0")).toBeInTheDocument();
    expect(screen.getByText("Nothing urgent.")).toBeInTheDocument();
    const names = screen.getAllByRole("link", { name: /Asha Traders|Calm Co/ });
    expect(names.map((name) => name.textContent)).toEqual(["Asha Traders", "Calm Co"]);
  });

  it("says where clients come from when there are none", async () => {
    open([]);

    expect(await screen.findByText(/No active clients yet/)).toBeInTheDocument();
  });
});
