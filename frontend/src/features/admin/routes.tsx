import type { RouteObject } from "react-router";

import { AdminDashboardPage } from "./pages/AdminDashboardPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";

/** Admin area pages of the admin module (paths are relative to /admin). */
export const routes: RouteObject[] = [
  { index: true, element: <AdminDashboardPage /> },
  { path: "users", element: <AdminUsersPage /> },
];
