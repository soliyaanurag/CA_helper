/**
 * API calls for the compliance module: TanStack Query hooks around the API client.
 * Every call goes through apiFetch(), so failures are ApiRequestError (code, message).
 */
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";

/** GET /api/v1/compliance/dashboard */
export function useComplianceDashboard() {
  return useQuery({
    queryKey: ["compliance", "dashboard"],
    queryFn: () => apiFetch("/api/v1/compliance/dashboard"),
  });
}
