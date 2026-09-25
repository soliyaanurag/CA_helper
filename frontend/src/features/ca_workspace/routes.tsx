import type { FeatureRoutes } from "@/core/routing";

import { CaWorkspacePage } from "./pages/CaWorkspacePage";
import { CaDashboardPage } from "./pages/CaDashboardPage";

/** Routes of the ca_workspace module, picked up automatically by core/routes.tsx. */
export const routes: FeatureRoutes = {
  ca: {
    routes: [
      { index: true, element: <CaDashboardPage /> },
      { path: "clients", element: <CaWorkspacePage /> },
    ],
    nav: [
      { label: "Dashboard", path: "", order: 0 },
      { label: "My clients", path: "clients", order: 10 },
    ],
  },
};
