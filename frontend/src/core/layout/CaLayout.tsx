import type { NavItem } from "@/core/routing";

import { AppShell } from "./AppShell";

/** Layout for the CA area (/ca). Route guards are not built yet. */
export function CaLayout({ nav }: { nav: NavItem[] }) {
  return <AppShell title="Chartered Accountant" nav={nav} />;
}
