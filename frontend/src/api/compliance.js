/**
 * API calls for the compliance module: TanStack Query hooks around the API client.
 * Every call goes through unwrap(), so failures are ApiRequestError (code, message, requestId).
 */
import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";

/** GET /api/v1/compliance/dashboard */
export function useComplianceDashboard() {
  return useQuery({
    queryKey: ["compliance", "dashboard"],
    queryFn: () => unwrap(api.GET("/api/v1/compliance/dashboard")),
  });
}
