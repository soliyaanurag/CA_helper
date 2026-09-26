import type { RouteObject } from "react-router";

import { CaDashboardPage } from "./pages/CaDashboardPage";
import { CaWorkspacePage } from "./pages/CaWorkspacePage";

/** CA area pages of the ca_workspace module (paths are relative to /ca). */
export const routes: RouteObject[] = [
  { index: true, element: <CaDashboardPage /> },
  { path: "clients", element: <CaWorkspacePage /> },
];
