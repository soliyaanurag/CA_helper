import type { FeatureRoutes } from "@/core/routing";

import { AlertsPage } from "./pages/AlertsPage";

/** Routes of the alerts module, picked up automatically by core/routes.tsx. */
export const routes: FeatureRoutes = {
  business: {
    routes: [{ path: "alerts", element: <AlertsPage /> }],
    nav: [{ label: "Notification settings", path: "alerts", order: 50 }],
  },
};
