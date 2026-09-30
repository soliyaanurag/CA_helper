import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const UPDATES = "/api/v1/regulatory/updates";

const CHANGE = {
  id: "0b8f4c1e-2d3a-4e5f-8a6b-7c8d9e0f1a2b",
  change_type: "due_date_extension",
  summary: "GSTR-3B for September 2026 can be filed until 31 October 2026.",
  form_codes: ["gstr_3b"],
  affected_categories: { extracted_by: "ai", gst_schemes: ["regular_qrmp"] },
  dates: { new_due_date: "2026-10-31", period: "September 2026" },
  created_at: "2026-09-28T02:00:00+00:00",
  notified_at: "2026-09-28T02:00:00+00:00",
  article_title: "GSTR-3B due date extended for September 2026",
  article_url: "https://news.example.com/a/1",
  published_at: "2026-09-28T04:30:00+00:00",
  source_name: "TaxGuru: GST news",
  match_count: 3,
};

const KEYWORDS_ONLY = {
  ...CHANGE,
  id: "1c9f5d2f-3e4b-4f6a-9b7c-8d9e0f1a2b3c",
  summary: "Possible change to GSTR-1 found in the news.",
  article_title: "GSTR-1 late fee news",
  article_url: "https://news.example.com/a/2",
  form_codes: ["gstr_1"],
  affected_categories: { extracted_by: "keywords" },
  dates: {},
  notified_at: null,
  match_count: 0,
};

describe("regulatory updates page", () => {
  it("lists the changes about my forms, marking those found by keywords", async () => {
    loginAs("business");
    fakeApi({ [`GET ${UPDATES}`]: [200, [CHANGE, KEYWORDS_ONLY]] });
    renderApp("/business/updates");

    expect(await screen.findByText(CHANGE.summary)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: CHANGE.article_title })).toHaveAttribute(
      "href",
      CHANGE.article_url,
    );
    expect(screen.getByText(KEYWORDS_ONLY.summary)).toBeInTheDocument();
    expect(screen.getAllByText("Found by keywords: read the article")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Regulatory updates" })).toHaveAttribute(
      "href",
      "/business/updates",
    );
  });

  it("says when there is nothing yet, for a CA too", async () => {
    loginAs("ca");
    fakeApi({ [`GET ${UPDATES}`]: [200, []] });
    renderApp("/ca/updates");

    expect(await screen.findByText("No changes about your forms yet.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Regulatory updates" })).toHaveAttribute(
      "href",
      "/ca/updates",
    );
  });
});
