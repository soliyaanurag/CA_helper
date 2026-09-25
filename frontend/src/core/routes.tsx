import type { RouteObject } from "react-router";

import { RequireRole } from "@/core/auth/RequireRole";
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
function areaChildren(area: Area, title: string): RouteObject[] {
  const routes = routesFor(area);
  if (routes.some((route) => route.index)) return routes;
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
  // Each area is only for its own role (RequireRole); the backend checks again.
  {
    path: AREA_PREFIX.business,
    element: (
      <RequireRole role="business">
        <BusinessLayout nav={navFor("business")} />
      </RequireRole>
    ),
    children: areaChildren("business", "Business"),
  },
  {
    path: AREA_PREFIX.ca,
    element: (
      <RequireRole role="ca">
        <CaLayout nav={navFor("ca")} />
      </RequireRole>
    ),
    children: areaChildren("ca", "Chartered Accountant"),
  },
  {
    path: AREA_PREFIX.admin,
    element: (
      <RequireRole role="admin">
        <AdminLayout nav={navFor("admin")} />
      </RequireRole>
    ),
    children: areaChildren("admin", "Admin"),
  },
  { path: "*", element: <NotFoundPage /> },
];
