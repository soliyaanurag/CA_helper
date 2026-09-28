import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeApi, loginAs, renderApp } from "@/test/utils";

const HISTORY = "/api/v1/assistant/history";

const QUESTION = {
  id: "m1",
  role: "user",
  content: "Can I file a nil GSTR-3B?",
  citations: [],
  ask_a_ca: false,
  ai_used: false,
  created_at: "2026-09-28T10:00:00Z",
};

function answer(fields = {}) {
  return {
    id: "m2",
    role: "assistant",
    content: "Yes, when there were no sales and no tax to pay [1].",
    citations: [
      {
        number: 1,
        title: "Filing a nil GSTR-3B (official FAQs)",
        url: "https://tutorial.gst.gov.in/userguide/returns/FAQs_gstr3b_online.htm",
        source_path: "content/faqs/gst-nil-gstr-3b.md",
        excerpt: "Form GSTR-3B can be filed as a nil return if there are no outward supplies.",
      },
    ],
    ask_a_ca: false,
    ai_used: true,
    created_at: "2026-09-28T10:00:01Z",
    ...fields,
  };
}

describe("AI assistant page", () => {
  it("offers example questions and asks one", async () => {
    loginAs("business");
    // The same object is read on every request, so the history can change after asking.
    const routes = {
      [`GET ${HISTORY}`]: [200, []],
      "POST /api/v1/assistant/ask": [200, {}],
    };
    const fetchMock = fakeApi(routes);
    renderApp("/business/assistant");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Can I file a nil GSTR-3B?" }));
    routes[`GET ${HISTORY}`] = [200, [QUESTION, answer()]];
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText(/no sales and no tax to pay/)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Filing a nil GSTR-3B (official FAQs)" }),
    ).toHaveAttribute(
      "href",
      "https://tutorial.gst.gov.in/userguide/returns/FAQs_gstr3b_online.htm",
    );
    const call = fetchMock.mock.calls.find(([path]) => path === "/api/v1/assistant/ask");
    expect(JSON.parse(call[1].body)).toEqual({ question: "Can I file a nil GSTR-3B?" });
  });

  it("suggests a CA and shows passages when the AI could not answer", async () => {
    loginAs("business");
    fakeApi({
      [`GET ${HISTORY}`]: [
        200,
        [
          QUESTION,
          answer({
            content: "The AI assistant cannot write an answer right now.",
            ai_used: false,
            ask_a_ca: true,
          }),
        ],
      ],
    });
    renderApp("/business/assistant");

    expect(await screen.findByRole("link", { name: /ask a CA/ })).toHaveAttribute(
      "href",
      "/business/marketplace",
    );
    await userEvent.setup().click(screen.getByText("Show the passage"));
    expect(screen.getByText(/can be filed as a nil return/)).toBeInTheDocument();
  });

  it("clears the conversation", async () => {
    loginAs("business");
    const fetchMock = fakeApi({
      [`GET ${HISTORY}`]: [200, [QUESTION, answer()]],
      [`DELETE ${HISTORY}`]: [204],
    });
    renderApp("/business/assistant");

    await userEvent.setup().click(await screen.findByRole("button", { name: "Clear" }));

    expect(await screen.findByRole("button", { name: "What is GSTR-2B?" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(true);
  });
});

describe("floating AI assistant", () => {
  it("opens from the round button on any business page", async () => {
    loginAs("business");
    fakeApi({ [`GET ${HISTORY}`]: [200, [QUESTION, answer()]] });
    renderApp("/business/documents");

    expect(screen.queryByRole("dialog", { name: "AI assistant" })).not.toBeInTheDocument();
    await userEvent
      .setup()
      .click(await screen.findByRole("button", { name: "Open the AI assistant" }));

    const panel = await screen.findByRole("dialog", { name: "AI assistant" });
    expect(await within(panel).findByText(/no sales and no tax to pay/)).toBeInTheDocument();
  });

  it("is there for CAs", async () => {
    loginAs("ca");
    fakeApi({});
    renderApp("/ca/profile");
    expect(
      await screen.findByRole("button", { name: "Open the AI assistant" }),
    ).toBeInTheDocument();
  });

  it("is not shown to admins", async () => {
    loginAs("admin");
    fakeApi({});
    renderApp("/admin");
    await waitFor(() => expect(screen.getByText("Log out")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Open the AI assistant" })).not.toBeInTheDocument();
  });

  it("is not doubled on the assistant page", async () => {
    loginAs("business");
    fakeApi({ [`GET ${HISTORY}`]: [200, []] });
    renderApp("/business/assistant");
    await screen.findByRole("heading", { name: "AI assistant" });
    expect(screen.queryByRole("button", { name: "Open the AI assistant" })).not.toBeInTheDocument();
  });
});
