import type { NavItem } from "@/core/routing";

import { AppShell } from "./AppShell";

/** Layout for the business area (/app). Route guards and the floating assistant are not built yet. */
export function BusinessLayout({ nav }: { nav: NavItem[] }) {
  return <AppShell title="Business" nav={nav} />;
}
