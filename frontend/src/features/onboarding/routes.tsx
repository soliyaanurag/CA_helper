import type { RouteObject } from "react-router";

import { OnboardingPage } from "./pages/OnboardingPage";

/** Business area pages of the onboarding module (paths are relative to /business). */
export const routes: RouteObject[] = [{ path: "onboarding", element: <OnboardingPage /> }];
