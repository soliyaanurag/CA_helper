/**
 * API calls for the compliance module: TanStack Query hooks around the typed client.
 * Every call goes through unwrap(), so failures are ApiRequestError (code, message).
 */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/core/api/client";
import { unwrap } from "@/core/api/errors";

/** GET /api/v1/compliance/dashboard */
export function useComplianceDashboard() {
  return useQuery({
    queryKey: ["compliance", "dashboard"],
    queryFn: () => unwrap(api.GET("/api/v1/compliance/dashboard")),
  });
}
