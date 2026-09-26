import type { RouteObject } from "react-router";

import { DocumentsPage } from "./pages/DocumentsPage";

/** Business area pages of the documents module (paths are relative to /business). */
export const routes: RouteObject[] = [{ path: "documents", element: <DocumentsPage /> }];
