import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fakeApi, renderApp } from "@/test/utils";

describe("landing page API status", () => {
  it("shows ok when the API and database are up", async () => {
    fakeApi({ "GET /api/health": [200, { status: "ok", database: "ok" }] });
    renderApp("/");

    expect(await screen.findByText("ok")).toBeInTheDocument();
  });

  it("tells a database outage apart from an unreachable API", async () => {
    fakeApi({ "GET /api/health": [503, { status: "degraded", database: "unavailable" }] });
    renderApp("/");

    expect(await screen.findByText("API up, database unavailable")).toBeInTheDocument();
  });
});
