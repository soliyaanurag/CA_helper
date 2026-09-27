import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

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

describe("landing page outside development", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("hides the API status while everything is up", async () => {
    vi.stubEnv("DEV", false);
    const fetchMock = fakeApi({ "GET /api/health": [200, { status: "ok", database: "ok" }] });
    renderApp("/");

    await screen.findByRole("heading", { name: "CA Helper" });
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByText(/API status/)).not.toBeInTheDocument();
  });

  it("still shows it when the API cannot be reached", async () => {
    vi.stubEnv("DEV", false);
    fakeApi({ "GET /api/health": [502, {}] });
    renderApp("/");

    expect(await screen.findByText("unreachable")).toBeInTheDocument();
  });
});

describe("landing page audience cards", () => {
  it("link to signup with the role chosen, and to login for admins", async () => {
    fakeApi({ "GET /api/health": [200, { status: "ok", database: "ok" }] });
    const router = renderApp("/");

    expect(await screen.findByRole("link", { name: /Admins/ })).toHaveAttribute("href", "/login");
    await userEvent.setup().click(screen.getByRole("link", { name: /Chartered Accountants/ }));

    expect(await screen.findByRole("heading", { name: "Create an account" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/signup");
    expect(screen.getByLabelText("Chartered Accountant")).toBeChecked();
  });
});
