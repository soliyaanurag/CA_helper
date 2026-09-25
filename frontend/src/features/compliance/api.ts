/**
 * API calls for the compliance module: TanStack Query hooks around the typed client.
 */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/core/api/client";

/** GET /api/v1/compliance/dashboard */
export function useComplianceDashboard() {
  return useQuery({
    queryKey: ["compliance", "dashboard"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/compliance/dashboard");
      if (error) throw new Error(error.error.message);
      return data;
    },
  });
}
