import type { FeatureRoutes } from "@/core/routing";

import { AdminUsersPage } from "./pages/AdminUsersPage";
import { AdminDashboardPage } from "./pages/AdminDashboardPage";

/** Routes of the admin module, picked up automatically by core/routes.tsx. */
export const routes: FeatureRoutes = {
  admin: {
    routes: [
      { index: true, element: <AdminDashboardPage /> },
      { path: "users", element: <AdminUsersPage /> },
    ],
    nav: [
      { label: "Dashboard", path: "", order: 0 },
      { label: "Users & CAs", path: "users", order: 10 },
    ],
  },
};
