import type { RouteObject } from "react-router";

/** The four app areas. Each has its own layout and URL prefix. */
export type Area = "public" | "business" | "ca" | "admin";

export const AREA_PREFIX: Record<Area, string> = {
  public: "",
  business: "/app",
  ca: "/ca",
  admin: "/admin",
};

/** A sidebar link. `path` is relative to the area prefix, e.g. "compliance". */
export interface NavItem {
  label: string;
  path: string;
  /** Lower numbers appear first (default 100). */
  order?: number;
}

/**
 * What every `features/<module>/routes.tsx` exports as `routes`.
 * Route paths are relative to the area prefix (so "compliance" in the
 * business area becomes /app/compliance). Admin screens owned by a module
 * go under `admin` and live in `features/<module>/admin/`.
 */
export type FeatureRoutes = Partial<Record<Area, { routes: RouteObject[]; nav?: NavItem[] }>>;
