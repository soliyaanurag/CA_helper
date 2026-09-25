import { QueryClient } from "@tanstack/react-query";

/** One TanStack Query cache for the whole app. */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});
