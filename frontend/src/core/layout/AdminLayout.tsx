import type { NavItem } from "@/core/routing";

import { AppShell } from "./AppShell";

/** Layout for the admin area (/admin). Module admin screens from features/<module>/admin/ appear here. */
export function AdminLayout({ nav }: { nav: NavItem[] }) {
  return <AppShell title="Admin" nav={nav} />;
}
