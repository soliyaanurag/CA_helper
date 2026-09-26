import type { RouteObject } from "react-router";

import { AssistantPage } from "./pages/AssistantPage";

/** Business area pages of the assistant module (paths are relative to /business). */
export const routes: RouteObject[] = [{ path: "assistant", element: <AssistantPage /> }];
