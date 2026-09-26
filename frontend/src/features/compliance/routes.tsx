import type { RouteObject } from "react-router";

import { BusinessDashboardPage } from "./pages/BusinessDashboardPage";
import { CompliancePage } from "./pages/CompliancePage";

/** Business area pages of the compliance module (paths are relative to /business). */
export const routes: RouteObject[] = [
  { index: true, element: <BusinessDashboardPage /> },
  { path: "compliance", element: <CompliancePage /> },
];
