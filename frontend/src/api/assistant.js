/**
 * All calls to the AI assistant backend (backend/app/routes/assistant.py).
 * Pages use these functions instead of calling the backend themselves.
 */
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";

// Name of the conversation in the query cache; AssistantChat refreshes it after each question.
export const ASSISTANT_HISTORY_KEY = ["assistant", "history"];

// The user's questions and answers, oldest first:
// [{ id, role: "user" | "assistant", content, citations, ask_a_ca, ai_used, created_at }].
export function useAssistantHistory() {
  return useQuery({
    queryKey: ASSISTANT_HISTORY_KEY,
    queryFn: () => apiFetch("/api/v1/assistant/history"),
  });
}

// Ask a question: { answer, citations: [{ number, title, url, source_path, excerpt }],
// ask_a_ca, ai_used }. The answer is also saved in the history.
export function askAssistant(question) {
  return apiFetch("/api/v1/assistant/ask", { method: "POST", body: { question } });
}

// Clear the conversation.
export function clearAssistantHistory() {
  return apiFetch("/api/v1/assistant/history", { method: "DELETE" });
}
