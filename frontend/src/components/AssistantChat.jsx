import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import {
  ASSISTANT_HISTORY_KEY,
  askAssistant,
  clearAssistantHistory,
  useAssistantHistory,
} from "@/api/assistant";
import { errorMessage } from "@/api/client";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";

// Questions to start with, shown while the conversation is empty.
const EXAMPLES = [
  "Can I file a nil GSTR-3B?",
  "What is GSTR-2B?",
  "Which ITR form is for a small business?",
];

/**
 * The AI assistant conversation (AS2-AS5), used by the floating AssistantWidget and the
 * /business/assistant page. Answers come from our guides and official FAQs and list their
 * sources; "Ask a CA" links to the marketplace for business owners.
 */
export function AssistantChat({ role }) {
  const history = useAssistantHistory();
  const queryClient = useQueryClient();
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const bottom = useRef(null);

  // Keep the newest message in view.
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [history.data, busy]);

  async function onSubmit(event) {
    event.preventDefault();
    const text = question.trim();
    if (text.length < 3) return;
    setError(null);
    setBusy(true);
    try {
      await askAssistant(text);
      setQuestion("");
      await queryClient.invalidateQueries({ queryKey: ASSISTANT_HISTORY_KEY });
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  async function onClear() {
    setError(null);
    try {
      await clearAssistantHistory();
      queryClient.setQueryData(ASSISTANT_HISTORY_KEY, []);
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }

  const messages = history.data || [];
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {history.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
        {history.isSuccess && messages.length === 0 && (
          <div className="space-y-2 text-sm">
            <p className="text-muted-foreground">
              Ask about GST, income-tax or TDS filings. Answers come from our guides and official
              FAQs, with their sources.
            </p>
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setQuestion(example)}
                className="block rounded-full border px-3 py-1 text-left text-sm hover:bg-muted"
              >
                {example}
              </button>
            ))}
          </div>
        )}
        {messages.map((message) =>
          message.role === "user" ? (
            <p
              key={message.id}
              className="ml-8 rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground"
            >
              {message.content}
            </p>
          ) : (
            <Answer key={message.id} message={message} role={role} />
          ),
        )}
        {busy && <p className="text-sm text-muted-foreground">Looking it up...</p>}
        <div ref={bottom} />
      </div>
      <form onSubmit={onSubmit} className="space-y-2 border-t p-3">
        <label htmlFor="assistant_question" className="sr-only">
          Your question
        </label>
        <textarea
          id="assistant_question"
          rows={2}
          maxLength={500}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Your question (no personal details, please)"
          className="w-full resize-none rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none focus-visible:border-ring"
        />
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="flex justify-between gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onClear}
            disabled={busy || messages.length === 0}
          >
            Clear
          </Button>
          <Button type="submit" size="sm" disabled={busy || question.trim().length < 3}>
            {busy ? "Asking..." : "Ask"}
          </Button>
        </div>
      </form>
    </div>
  );
}

/** One answer: the text, its sources, and "Ask a CA" when a professional should look. */
function Answer({ message, role }) {
  return (
    <div className="mr-4 space-y-2 rounded-lg bg-muted px-3 py-2">
      <Markdown>{message.content}</Markdown>
      {message.citations.length > 0 && (
        <ol className="space-y-1 text-xs text-muted-foreground">
          {message.citations.map((citation) => (
            <li key={citation.number}>
              [{citation.number}]{" "}
              {citation.url ? (
                <a href={citation.url} target="_blank" rel="noreferrer" className="underline">
                  {citation.title}
                </a>
              ) : (
                <span>{citation.title} (our guide)</span>
              )}
              {!message.ai_used && (
                <details className="mt-1">
                  <summary className="cursor-pointer">Show the passage</summary>
                  <div className="mt-1 text-foreground">
                    <Markdown>{citation.excerpt}</Markdown>
                  </div>
                </details>
              )}
            </li>
          ))}
        </ol>
      )}
      {message.ask_a_ca && role === "business" && (
        <Link to="/business/marketplace" className="block text-sm text-primary hover:underline">
          This may need a professional: ask a CA →
        </Link>
      )}
      {message.ask_a_ca && role === "ca" && (
        <p className="text-xs text-muted-foreground">This may need a professional's judgment.</p>
      )}
    </div>
  );
}
