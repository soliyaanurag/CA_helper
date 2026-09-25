/**
 * API calls for the ca_workspace module: TanStack Query hooks around the typed client.
 */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/core/api/client";

/** GET /api/v1/ca-workspace/dashboard */
export function useCaDashboard() {
  return useQuery({
    queryKey: ["ca_workspace", "dashboard"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/ca-workspace/dashboard");
      if (error) throw new Error(error.error.message);
      return data;
    },
  });
}
