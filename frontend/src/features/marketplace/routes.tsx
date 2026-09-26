import type { RouteObject } from "react-router";

import { MarketplacePage } from "./pages/MarketplacePage";

/** Business area pages of the marketplace module (paths are relative to /business). */
export const routes: RouteObject[] = [{ path: "marketplace", element: <MarketplacePage /> }];
