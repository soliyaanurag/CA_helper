import type { NavItem } from "@/core/routing";

import { AppShell } from "./AppShell";

/** Layout for the CA area (/ca). Guards are added in Phase 1 (FE-02). */
export function CaLayout({ nav }: { nav: NavItem[] }) {
  return <AppShell title="Chartered Accountant" nav={nav} />;
}
