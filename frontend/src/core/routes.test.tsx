import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter } from "react-router";
import { RouterProvider } from "react-router/dom";
import { describe, expect, it } from "vitest";

import { appRoutes, featureRoutes } from "./routes";

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

function renderAt(path: string) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("route aggregation", () => {
  it("collects routes from every feature module", () => {
    expect(Object.keys(featureRoutes).sort()).toEqual(MODULES);
  });

  it("renders a module page inside its area layout, with every module's nav link", async () => {
    renderAt("/app/compliance");

    expect(await screen.findByRole("heading", { name: "Compliance calendar" })).toBeInTheDocument();
    // Nav links come from other modules' routes.tsx files.
    expect(screen.getByRole("link", { name: "Document vault" })).toHaveAttribute(
      "href",
      "/app/documents",
    );
  });

  it("registers module admin screens in the admin area", async () => {
    renderAt("/admin/regulatory");

    expect(await screen.findByRole("heading", { name: "Regulatory news" })).toBeInTheDocument();
  });
});
