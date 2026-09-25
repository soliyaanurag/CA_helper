import { USER_ROLE_LABELS } from "@/core/labels";
import { AREA_PREFIX, type NavItem } from "@/core/routing";

import { AppShell } from "./AppShell";

/** Layout for the admin area (/admin). Module admin screens from features/<module>/admin/ appear here. Guarded by RequireRole in core/routes.tsx. */
export function AdminLayout({ nav }: { nav: NavItem[] }) {
  return <AppShell title={USER_ROLE_LABELS.admin} home={AREA_PREFIX.admin} nav={nav} />;
}
