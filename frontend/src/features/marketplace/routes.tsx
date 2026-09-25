import type { FeatureRoutes } from "@/core/routing";

import { MarketplacePage } from "./pages/MarketplacePage";

/** Routes of the marketplace module, picked up automatically by core/routes.tsx. */
export const routes: FeatureRoutes = {
  business: {
    routes: [{ path: "marketplace", element: <MarketplacePage /> }],
    nav: [{ label: "Find a CA", path: "marketplace", order: 40 }],
  },
};
