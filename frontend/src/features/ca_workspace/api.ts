/**
 * API calls for the ca_workspace module: TanStack Query hooks around the typed client.
 * Every call goes through unwrap(), so failures are ApiRequestError (code, message).
 */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/core/api/client";
import { unwrap } from "@/core/api/errors";

/** GET /api/v1/ca-workspace/dashboard */
export function useCaDashboard() {
  return useQuery({
    queryKey: ["ca_workspace", "dashboard"],
    queryFn: () => unwrap(api.GET("/api/v1/ca-workspace/dashboard")),
  });
}
