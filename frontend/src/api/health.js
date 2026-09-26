import { useQuery } from "@tanstack/react-query";

/**
 * GET /api/health: is the backend up, and can it reach its database?
 * 200 -> {status: "ok", database: "ok"}; 503 -> {status: "degraded", database: "unavailable"}
 * (the API answers, but the database is down). Only a failed request is an error.
 * Plain fetch, not apiFetch(): the 503 body is data to show, not the standard error body.
 */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const response = await fetch("/api/health");
      if (response.ok || response.status === 503) return response.json();
      throw new Error(`API returned HTTP ${response.status}`);
    },
    retry: false,
  });
}
