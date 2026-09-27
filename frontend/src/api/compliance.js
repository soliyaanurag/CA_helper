/**
 * All calls to the compliance backend (backend/app/routes/compliance.py).
 * Pages use these functions instead of calling the backend themselves.
 */
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";

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
