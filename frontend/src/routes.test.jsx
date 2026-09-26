import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

import { NAV } from "./routes";

describe("routes", () => {
  it("gives every sidebar link a path inside its role's area", () => {
    for (const [role, items] of Object.entries(NAV)) {
      for (const item of items) expect(item.path).toMatch(new RegExp(`^/${role}(/|$)`));
    }
  });

  it("renders a page inside its area layout, with the role's sidebar links", async () => {
    loginAs("business");
    fakeApi({});
    renderApp("/business/compliance");

    expect(await screen.findByRole("heading", { name: "Compliance calendar" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Document vault" })).toHaveAttribute(
      "href",
      "/business/documents",
    );
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/business");
  });

  it("shows the dashboard as the area home", async () => {
    loginAs("business");
    fakeApi({ "GET /api/v1/compliance/dashboard": [200, { message: "Welcome, Test business" }] });
    renderApp("/business");

    expect(
      await screen.findByRole("heading", { name: "Welcome, Test business" }),
    ).toBeInTheDocument();
  });

  it("serves admin screens in the admin area", async () => {
    loginAs("admin");
    fakeApi({});
    renderApp("/admin/regulatory");

    expect(await screen.findByRole("heading", { name: "Regulatory news" })).toBeInTheDocument();
  });
});
