import { USER_ROLE_LABELS } from "@/core/labels";
import { AREA_PREFIX, type NavItem } from "@/core/routing";

import { AppShell } from "./AppShell";

/** Layout for the business area (/business). The floating assistant is not built yet. Guarded by RequireRole in core/routes.tsx. */
export function BusinessLayout({ nav }: { nav: NavItem[] }) {
  return <AppShell title={USER_ROLE_LABELS.business} home={AREA_PREFIX.business} nav={nav} />;
}
