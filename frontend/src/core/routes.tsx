import type { RouteObject } from "react-router";

import { AdminLayout } from "@/core/layout/AdminLayout";
import { BusinessLayout } from "@/core/layout/BusinessLayout";
import { CaLayout } from "@/core/layout/CaLayout";
import { PublicLayout } from "@/core/layout/PublicLayout";
import { AreaIndexPage } from "@/core/pages/AreaIndexPage";
import { HomePage } from "@/core/pages/HomePage";
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

/** Sidebar links for one area, with absolute paths, sorted by `order`. */
export function navFor(area: Area): NavItem[] {
  return Object.values(featureRoutes)
    .flatMap((feature) => feature[area]?.nav ?? [])
    .map((item) => ({ ...item, path: `${AREA_PREFIX[area]}/${item.path}` }))
    .sort((a, b) => (a.order ?? 100) - (b.order ?? 100));
}

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    element: <PublicLayout />,
    children: [{ index: true, element: <HomePage /> }, ...routesFor("public")],
  },
  {
    path: AREA_PREFIX.business,
    element: <BusinessLayout nav={navFor("business")} />,
    children: [
      { index: true, element: <AreaIndexPage title="Business" nav={navFor("business")} /> },
      ...routesFor("business"),
    ],
  },
  {
    path: AREA_PREFIX.ca,
    element: <CaLayout nav={navFor("ca")} />,
    children: [
      { index: true, element: <AreaIndexPage title="Chartered Accountant" nav={navFor("ca")} /> },
      ...routesFor("ca"),
    ],
  },
  {
    path: AREA_PREFIX.admin,
    element: <AdminLayout nav={navFor("admin")} />,
    children: [
      { index: true, element: <AreaIndexPage title="Admin" nav={navFor("admin")} /> },
      ...routesFor("admin"),
    ],
  },
  { path: "*", element: <NotFoundPage /> },
];
