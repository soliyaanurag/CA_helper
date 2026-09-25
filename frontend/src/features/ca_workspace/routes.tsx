import type { FeatureRoutes } from "@/core/routing";

import { CaWorkspacePage } from "./pages/CaWorkspacePage";

/** Routes of the ca_workspace module, picked up automatically by core/routes.tsx. */
export const routes: FeatureRoutes = {
  ca: {
    routes: [{ path: "clients", element: <CaWorkspacePage /> }],
    nav: [{ label: "My clients", path: "clients", order: 10 }],
  },
};
