import type { FeatureRoutes } from "@/core/routing";

import { AdminUsersPage } from "./pages/AdminUsersPage";

/** Routes of the admin module, picked up automatically by core/routes.tsx. */
export const routes: FeatureRoutes = {
  admin: {
    routes: [{ path: "users", element: <AdminUsersPage /> }],
    nav: [{ label: "Users & CAs", path: "users", order: 10 }],
  },
};
