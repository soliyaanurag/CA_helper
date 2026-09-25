import type { FeatureRoutes } from "@/core/routing";

import { RegulatoryAdminPage } from "./admin/RegulatoryAdminPage";

/** Routes of the regulatory module, picked up automatically by core/routes.tsx. */
export const routes: FeatureRoutes = {
  admin: {
    routes: [{ path: "regulatory", element: <RegulatoryAdminPage /> }],
    nav: [{ label: "Regulatory news", path: "regulatory", order: 20 }],
  },
};
