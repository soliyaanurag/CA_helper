import type { RouteObject } from "react-router";

/** The four app areas. Each has its own layout and URL prefix. */
export type Area = "public" | "business" | "ca" | "admin";

export const AREA_PREFIX: Record<Area, string> = {
  public: "",
  business: "/business",
  ca: "/ca",
  admin: "/admin",
};

/** A sidebar link. `path` is relative to the area prefix, e.g. "compliance" ("" = area home). */
export interface NavItem {
  label: string;
  path: string;
  /** Lower numbers appear first (default 100). */
  order?: number;
}

/**
 * What every `features/<module>/routes.tsx` exports as `routes`.
 * Route paths are relative to the area prefix (so "compliance" in the
 * business area becomes /business/compliance). A module may give its area's home
 * page as an `index: true` route (e.g. the business dashboard in compliance);
 * without one the area shows AreaIndexPage. A nav item with path "" links to
 * the area home. Admin screens owned by a module go under `admin` and live in
 * `features/<module>/admin/`.
 */
export type FeatureRoutes = Partial<Record<Area, { routes: RouteObject[]; nav?: NavItem[] }>>;
