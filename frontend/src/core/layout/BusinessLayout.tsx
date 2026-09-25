import type { NavItem } from "@/core/routing";

import { AppShell } from "./AppShell";

/** Layout for the business area (/app). Guards and the floating assistant are added in Phase 1 (FE-02, FE-03). */
export function BusinessLayout({ nav }: { nav: NavItem[] }) {
  return <AppShell title="Business" nav={nav} />;
}
