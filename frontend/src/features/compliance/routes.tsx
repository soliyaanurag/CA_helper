import type { FeatureRoutes } from "@/core/routing";

import { CompliancePage } from "./pages/CompliancePage";
import { BusinessDashboardPage } from "./pages/BusinessDashboardPage";

/** Routes of the compliance module, picked up automatically by core/routes.tsx. */
export const routes: FeatureRoutes = {
  business: {
    routes: [
      { index: true, element: <BusinessDashboardPage /> },
      { path: "compliance", element: <CompliancePage /> },
    ],
    nav: [
      { label: "Dashboard", path: "", order: 0 },
      { label: "Compliance calendar", path: "compliance", order: 20 },
    ],
  },
};
