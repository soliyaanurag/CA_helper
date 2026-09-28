import { useState } from "react";
import { useLocation } from "react-router";

import { AssistantChat } from "@/components/AssistantChat";

/**
 * The floating AI assistant: a round button at the bottom right of every page (business
 * owners and CAs; AppShell adds it) that opens the conversation in a small panel.
 * Hidden on the full-page assistant (/business/assistant).
 */
export function AssistantWidget({ role }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  if (pathname.endsWith("/assistant")) return null;

  return (
    <div className="fixed right-6 bottom-6 z-50 flex flex-col items-end gap-3">
      {open && (
        <div
          role="dialog"
          aria-label="AI assistant"
          className="flex h-[32rem] w-96 max-w-[calc(100vw-3rem)] flex-col rounded-xl border bg-background shadow-xl"
        >
          <div className="flex items-center justify-between border-b px-3 py-2">
            <p className="text-sm font-semibold">AI assistant</p>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close the AI assistant"
              className="rounded px-2 text-muted-foreground hover:bg-muted"
            >
              ✕
            </button>
          </div>
          <AssistantChat role={role} />
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-label={open ? "Close the AI assistant" : "Open the AI assistant"}
        aria-expanded={open}
        className="h-14 w-14 rounded-full bg-primary text-sm font-semibold text-primary-foreground shadow-lg hover:opacity-90"
      >
        AI
      </button>
    </div>
  );
}
