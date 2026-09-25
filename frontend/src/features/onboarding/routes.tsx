import type { FeatureRoutes } from "@/core/routing";

import { OnboardingPage } from "./pages/OnboardingPage";

/** Routes of the onboarding module, picked up automatically by core/routes.tsx. */
export const routes: FeatureRoutes = {
  business: {
    routes: [{ path: "onboarding", element: <OnboardingPage /> }],
    nav: [{ label: "Business profile", path: "onboarding", order: 10 }],
  },
};
