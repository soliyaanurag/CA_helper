import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

import { featureRoutes } from "./routes";

const MODULES = [
  "admin",
  "alerts",
  "assistant",
  "ca_workspace",
  "compliance",
  "documents",
  "marketplace",
  "onboarding",
  "regulatory",
];

describe("route aggregation", () => {
  it("collects routes from every feature module", () => {
    expect(Object.keys(featureRoutes).sort()).toEqual(MODULES);
  });

  it("renders a module page inside its area layout, with every module's nav link", async () => {
    loginAs("business");
    fakeApi({});
    renderApp("/business/compliance");

    expect(await screen.findByRole("heading", { name: "Compliance calendar" })).toBeInTheDocument();
    // Nav links come from other modules' routes.tsx files.
    expect(screen.getByRole("link", { name: "Document vault" })).toHaveAttribute(
      "href",
      "/business/documents",
    );
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/business");
  });

  it("uses a module's index route as the area home", async () => {
    loginAs("business");
    fakeApi({ "GET /api/v1/compliance/dashboard": [200, { message: "Welcome, Test business" }] });
    renderApp("/business");

    expect(
      await screen.findByRole("heading", { name: "Welcome, Test business" }),
    ).toBeInTheDocument();
  });

  it("registers module admin screens in the admin area", async () => {
    loginAs("admin");
    fakeApi({});
    renderApp("/admin/regulatory");

    expect(await screen.findByRole("heading", { name: "Regulatory news" })).toBeInTheDocument();
  });
});
