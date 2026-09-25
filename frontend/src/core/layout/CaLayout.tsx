import { USER_ROLE_LABELS } from "@/core/labels";
import { AREA_PREFIX, type NavItem } from "@/core/routing";

import { AppShell } from "./AppShell";

/** Layout for the CA area (/ca). Guarded by RequireRole in core/routes.tsx. */
export function CaLayout({ nav }: { nav: NavItem[] }) {
  return <AppShell title={USER_ROLE_LABELS.ca} home={AREA_PREFIX.ca} nav={nav} />;
}
