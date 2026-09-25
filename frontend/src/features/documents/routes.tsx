import type { FeatureRoutes } from "@/core/routing";

import { DocumentsPage } from "./pages/DocumentsPage";

/** Routes of the documents module, picked up automatically by core/routes.tsx. */
export const routes: FeatureRoutes = {
  business: {
    routes: [{ path: "documents", element: <DocumentsPage /> }],
    nav: [{ label: "Document vault", path: "documents", order: 30 }],
  },
};
