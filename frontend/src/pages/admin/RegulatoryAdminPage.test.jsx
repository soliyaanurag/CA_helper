import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

// /admin/regulatory: the changes found in the news, and the news sources.

const CHANGES = "/api/v1/admin/regulatory/changes";

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

function routes(extra) {
  return {
    [`GET ${CHANGES}`]: [200, [CHANGE]],
    ...extra,
  };
}

describe("regulatory news page", () => {
  it("shows a change with its article and who it is for", async () => {
    loginAs("admin");
    fakeApi(routes({}));
    renderApp("/admin/regulatory");

    expect(await screen.findByText(CHANGE.summary)).toBeInTheDocument();
    expect(screen.getByText("Due date extension")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: CHANGE.article_title })).toHaveAttribute(
      "href",
      CHANGE.article_url,
    );
    expect(screen.getByText("GST scheme: Regular (quarterly, QRMP)")).toBeInTheDocument();
    expect(screen.getByText("September 2026")).toBeInTheDocument();
  });

  it("says how many businesses a change was sent to", async () => {
    loginAs("admin");
    fakeApi(routes({}));
    renderApp("/admin/regulatory");

    expect(await screen.findByText(/3 business\(es\) told/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve and notify" })).not.toBeInTheDocument();
  });

  it("says when a change was found without AI", async () => {
    loginAs("admin");
    fakeApi(
      routes({
        [`GET ${CHANGES}`]: [
          200,
          [
            {
              ...CHANGE,
              affected_categories: { extracted_by: "keywords" },
              notified_at: null,
              match_count: 0,
            },
          ],
        ],
      }),
    );
    renderApp("/admin/regulatory");

    expect(await screen.findByText("Found by keywords: read the article")).toBeInTheDocument();
    expect(screen.getByText("Everyone with an open filing of these forms")).toBeInTheDocument();
    expect(screen.getByText("Not sent to anyone")).toBeInTheDocument();
  });

  it("lists the sources and runs a scan", async () => {
    loginAs("admin");
    fakeApi(
      routes({
        "GET /api/v1/admin/regulatory/sources": [
          200,
          [
            {
              id: "5a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
              name: "TaxGuru: GST news",
              url: "https://taxguru.in/category/goods-and-service-tax/feed/",
              kind: "rss",
              enabled: true,
            },
          ],
        ],
        "POST /api/v1/admin/regulatory/scan": [
          200,
          { sources: 1, blocked_by_robots: 0, failed: 0, new_articles: 4, changes: 1 },
        ],
      }),
    );
    renderApp("/admin/regulatory");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("tab", { name: "Sources" }));
    expect(await screen.findByText("TaxGuru: GST news")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Switch off" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Scan now" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "4 new article(s), 1 change(s) found.",
    );
  });
});
