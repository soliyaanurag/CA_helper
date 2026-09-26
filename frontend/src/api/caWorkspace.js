/**
 * API calls for the ca_workspace module: TanStack Query hooks around the API client.
 * Every call goes through apiFetch(), so failures are ApiRequestError (code, message).
 */
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";

/** GET /api/v1/ca-workspace/dashboard */
export function useCaDashboard() {
  return useQuery({
    queryKey: ["ca_workspace", "dashboard"],
    queryFn: () => apiFetch("/api/v1/ca-workspace/dashboard"),
  });
}
