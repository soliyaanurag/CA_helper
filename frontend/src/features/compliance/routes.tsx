import type { FeatureRoutes } from "@/core/routing";

import { CompliancePage } from "./pages/CompliancePage";

/** Routes of the compliance module, picked up automatically by core/routes.tsx. */
export const routes: FeatureRoutes = {
  business: {
    routes: [{ path: "compliance", element: <CompliancePage /> }],
    nav: [{ label: "Compliance calendar", path: "compliance", order: 20 }],
  },
};
