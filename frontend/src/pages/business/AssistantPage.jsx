import { AssistantChat } from "@/components/AssistantChat";

/** /business/assistant: the AI assistant on a full page (the same chat as the floating one). */
export function AssistantPage() {
  return (
    <div className="flex h-[calc(100vh-4rem)] max-w-3xl flex-col space-y-2">
      <h1 className="text-2xl font-semibold">AI assistant</h1>
      <p className="text-sm text-muted-foreground">
        Answers come from our guides and official FAQs, with their sources. It is not legal advice:
        for your own case, ask a CA.
      </p>
      <div className="flex min-h-0 flex-1 flex-col rounded-xl border">
        <AssistantChat role="business" />
      </div>
    </div>
  );
}
