import { useQuery } from "@tanstack/react-query";

import { api } from "./client";

/**
 * GET /api/health: is the backend up, and can it reach its database?
 * 200 -> {status: "ok"}; 503 -> {status: "degraded", database: "unavailable"}
 * (the API answers, but the database is down). Only a failed request is an error.
 */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/health");
      if (data) return data;
      if (response.status === 503 && error && "database" in error) return error;
      throw new Error(`API returned HTTP ${response.status}`);
    },
    retry: false,
  });
}
