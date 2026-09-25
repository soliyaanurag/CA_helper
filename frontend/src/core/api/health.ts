import { useQuery } from "@tanstack/react-query";

import { api } from "./client";

/** GET /api/health: shows whether the backend and its database are reachable. */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/health");
      if (error) throw new Error(`API returned HTTP ${response.status}`);
      return data;
    },
    retry: false,
  });
}
