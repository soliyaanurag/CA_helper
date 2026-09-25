import { AREA_PREFIX, type NavItem } from "@/core/routing";

import { AppShell } from "./AppShell";

/** Layout for the business area (/business). The floating assistant is not built yet. Guarded by RequireRole in core/routes.tsx. */
export function BusinessLayout({ nav }: { nav: NavItem[] }) {
  return <AppShell title="Business" home={AREA_PREFIX.business} nav={nav} />;
}
