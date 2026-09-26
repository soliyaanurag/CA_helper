/**
 * API calls for the admin module: TanStack Query hooks around the API client.
 * Every call goes through apiFetch(), so failures are ApiRequestError (code, message).
 */
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";

/** GET /api/v1/admin/dashboard */
export function useAdminDashboard() {
  return useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: () => apiFetch("/api/v1/admin/dashboard"),
  });
}
