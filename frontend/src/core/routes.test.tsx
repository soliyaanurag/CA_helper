import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

describe("app routes", () => {
  it("renders a feature page inside its area, with the area's sidebar links", async () => {
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

  it("uses a feature's index route as the area home", async () => {
    loginAs("business");
    fakeApi({ "GET /api/v1/compliance/dashboard": [200, { message: "Welcome, Test business" }] });
    renderApp("/business");

    expect(
      await screen.findByRole("heading", { name: "Welcome, Test business" }),
    ).toBeInTheDocument();
  });

  it("lists a feature's admin screen in the admin area", async () => {
    loginAs("admin");
    fakeApi({});
    renderApp("/admin/regulatory");

    expect(await screen.findByRole("heading", { name: "Regulatory news" })).toBeInTheDocument();
  });
});
