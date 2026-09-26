import type { RouteObject } from "react-router";

import { RegulatoryAdminPage } from "./admin/RegulatoryAdminPage";

/** Admin area pages of the regulatory module (paths are relative to /admin). */
export const routes: RouteObject[] = [{ path: "regulatory", element: <RegulatoryAdminPage /> }];
