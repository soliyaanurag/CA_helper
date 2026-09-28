/**
 * All calls to the compliance backend (backend/app/routes/compliance.py).
 * Pages use these functions instead of calling the backend themselves.
 */
import { useQuery } from "@tanstack/react-query";

import { apiDownload, apiFetch } from "@/api/client";

// Name of the filings list in the query cache. OnboardingPage refreshes it after registering.
export const FILINGS_KEY = ["compliance", "items"];

/** GET /api/v1/compliance/dashboard */
export function useComplianceDashboard() {
  return useQuery({
    queryKey: ["compliance", "dashboard"],
    queryFn: () => apiFetch("/api/v1/compliance/dashboard"),
  });
}

// The business's filings, soonest due first.
// Returns null if the business is not registered yet (the backend answers 404).
async function fetchFilings() {
  try {
    return await apiFetch("/api/v1/compliance/items");
  } catch (error) {
    if (error.code === "BUSINESS_NOT_FOUND") {
      return null;
    }
    throw error;
  }
}

// Used by CompliancePage.
export function useFilings() {
  return useQuery({ queryKey: FILINGS_KEY, queryFn: fetchFilings });
}

// --- One filing's page (CO5, CO7, CO8, CO9) -----------------------------------------

// Name of one filing in the query cache. The actions below return the updated filing,
// and FilingPage puts it there.
export function filingKey(itemId) {
  return ["compliance", "item", itemId];
}

// { filing, form_name, content_status, explanation, instructions, checklist, acknowledgement }
export function useFiling(itemId) {
  return useQuery({
    queryKey: filingKey(itemId),
    queryFn: () => apiFetch("/api/v1/compliance/items/" + itemId),
  });
}

// path is "self" (file it myself) or "ca" (with a CA).
export function chooseFilingPath(itemId, path) {
  return apiFetch("/api/v1/compliance/items/" + itemId + "/path", {
    method: "POST",
    body: { path },
  });
}

// Tick (ticked = true) or untick one document of the checklist.
export function tickChecklist(itemId, key, ticked) {
  return apiFetch("/api/v1/compliance/items/" + itemId + "/checklist", {
    method: "POST",
    body: { key, ticked },
  });
}

// "I filed it myself". Both the ARN and the file are optional.
export function markFiled(itemId, acknowledgementNo, file) {
  const form = new FormData();
  if (acknowledgementNo) form.append("acknowledgement_no", acknowledgementNo);
  if (file) form.append("file", file);
  return apiFetch("/api/v1/compliance/items/" + itemId + "/mark-filed", {
    method: "POST",
    body: form,
  });
}

// Undo a mistaken "mark as filed".
export function unmarkFiled(itemId) {
  return apiFetch("/api/v1/compliance/items/" + itemId + "/unmark-filed", { method: "POST" });
}

// The uploaded acknowledgement file (a Blob), loaded only when there is one.
export function useAcknowledgementFile(itemId, enabled) {
  return useQuery({
    queryKey: [...filingKey(itemId), "acknowledgement"],
    queryFn: () => apiDownload("/api/v1/compliance/items/" + itemId + "/acknowledgement"),
    enabled,
  });
}
