import type { RouteObject } from "react-router";

import { AlertsPage } from "./pages/AlertsPage";

/** Business area pages of the alerts module (paths are relative to /business). */
export const routes: RouteObject[] = [{ path: "alerts", element: <AlertsPage /> }];
