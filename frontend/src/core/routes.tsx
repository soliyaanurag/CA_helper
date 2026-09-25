import type { ComponentType } from "react";
import type { RouteObject } from "react-router";

import { RequireRole } from "@/core/auth/RequireRole";
import type { Role } from "@/core/auth/session";
import { USER_ROLE_LABELS } from "@/core/labels";
import { AdminLayout } from "@/core/layout/AdminLayout";
import { BusinessLayout } from "@/core/layout/BusinessLayout";
import { CaLayout } from "@/core/layout/CaLayout";
import { PublicLayout } from "@/core/layout/PublicLayout";
import { AreaIndexPage } from "@/core/pages/AreaIndexPage";
import { HomePage } from "@/core/pages/HomePage";
import { LoginPage } from "@/core/pages/LoginPage";
import { NotFoundPage } from "@/core/pages/NotFoundPage";
import { AREA_PREFIX, type Area, type FeatureRoutes, type NavItem } from "@/core/routing";

/**
 * Route aggregation: every `features/<module>/routes.tsx` is picked up
 * automatically at build time. There is no central list to edit, so modules
 * never conflict here.
 */
const featureFiles = import.meta.glob<{ routes: FeatureRoutes }>("../features/*/routes.tsx", {
  eager: true,
});

/** Module name -> its routes, e.g. "compliance" -> { business: {...} }. */
export const featureRoutes: Record<string, FeatureRoutes> = Object.fromEntries(
  Object.entries(featureFiles).map(([file, mod]) => [file.split("/")[2], mod.routes]),
);

function routesFor(area: Area): RouteObject[] {
  return Object.values(featureRoutes).flatMap((feature) => feature[area]?.routes ?? []);
}

/** The area's routes, plus AreaIndexPage as its home if no module gives an index route. */
function areaChildren(area: Area): RouteObject[] {
  const routes = routesFor(area);
  if (routes.some((route) => route.index)) return routes;
  const title = area === "public" ? "" : USER_ROLE_LABELS[area];
  return [{ index: true, element: <AreaIndexPage title={title} nav={navFor(area)} /> }, ...routes];
}

/** Sidebar links for one area, with absolute paths, sorted by `order`. */
export function navFor(area: Area): NavItem[] {
  return Object.values(featureRoutes)
    .flatMap((feature) => feature[area]?.nav ?? [])
    .map((item) => ({
      ...item,
      path: item.path ? `${AREA_PREFIX[area]}/${item.path}` : AREA_PREFIX[area],
    }))
    .sort((a, b) => (a.order ?? 100) - (b.order ?? 100));
}

/** The logged-in areas: one per role, each with its own layout. */
const ROLE_LAYOUTS: Record<Role, ComponentType<{ nav: NavItem[] }>> = {
  business: BusinessLayout,
  ca: CaLayout,
  admin: AdminLayout,
};

function roleArea(role: Role): RouteObject {
  const Layout = ROLE_LAYOUTS[role];
  return {
    path: AREA_PREFIX[role],
    // Only for this role (RequireRole); the backend checks again on every request.
    element: (
      <RequireRole role={role}>
        <Layout nav={navFor(role)} />
      </RequireRole>
    ),
    children: areaChildren(role),
  };
}

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    element: <PublicLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "login", element: <LoginPage /> },
      ...routesFor("public"),
    ],
  },
  ...(Object.keys(ROLE_LAYOUTS) as Role[]).map(roleArea),
  { path: "*", element: <NotFoundPage /> },
];
