import type { FeatureRoutes } from "@/core/routing";

import { AssistantPage } from "./pages/AssistantPage";

/** Routes of the assistant module, picked up automatically by core/routes.tsx. */
export const routes: FeatureRoutes = {
  business: {
    routes: [{ path: "assistant", element: <AssistantPage /> }],
    nav: [{ label: "AI assistant", path: "assistant", order: 60 }],
  },
};
