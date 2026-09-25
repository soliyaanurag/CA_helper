/**
 * API calls for the admin module: TanStack Query hooks around the typed client.
 * Every call goes through unwrap(), so failures are ApiRequestError (code, message, requestId).
 */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/core/api/client";
import { unwrap } from "@/core/api/errors";

/** GET /api/v1/admin/dashboard */
export function useAdminDashboard() {
  return useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/dashboard")),
  });
}
