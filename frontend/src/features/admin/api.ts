/**
 * API calls for the admin module: TanStack Query hooks around the typed client.
 */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/core/api/client";

/** GET /api/v1/admin/dashboard */
export function useAdminDashboard() {
  return useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/dashboard");
      if (error) throw new Error(error.error.message);
      return data;
    },
  });
}
