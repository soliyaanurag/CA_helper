import { Link, NavLink, Outlet } from "react-router";

import { AssistantWidget } from "@/components/AssistantWidget";
import { NotificationBell } from "@/components/NotificationBell";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { USER_ROLE_LABELS } from "@/lib/labels";
import { ROLE_HOME } from "@/lib/session";
import { cn } from "@/lib/utils";

/**
 * Layout for the logged-in areas (/business, /ca, /admin): sidebar with the
 * notification bell, the role's links, user name, change password + logout, the
 * current page (<Outlet />) and, for business owners and CAs, the floating AI assistant.
 * `nav` is a list of { label, path } links (NAV in routes.jsx).
 *
 * The sidebar is exactly one screen tall and stays in place while the page scrolls
 * (sticky top-0 h-screen), so the name, "Change password" and "Log out" are always
 * visible at its bottom. If there are more links than fit, only the link list scrolls.
 */
export function AppShell({ role, nav }) {
  const { user, logout } = useAuth();
  const title = USER_ROLE_LABELS[role];
  const home = ROLE_HOME[role];

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r bg-muted/40 p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <Link to={home} className="text-lg font-semibold">
              CA Helper
            </Link>
            <p className="text-xs text-muted-foreground">{title}</p>
          </div>
          <NotificationBell />
        </div>
        <nav
          className="mt-6 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto"
          aria-label={`${title} navigation`}
        >
          {nav.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === home} // the home link is active only on the home page
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-2 text-sm",
                  isActive ? "bg-primary text-primary-foreground" : "hover:bg-muted",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-2 border-t pt-4">
          <p className="truncate text-sm">{user?.full_name}</p>
          <Button asChild variant="ghost" size="sm" className="w-full">
            <Link to={`${home}/change-password`}>Change password</Link>
          </Button>
          <Button variant="outline" size="sm" className="w-full" onClick={logout}>
            Log out
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-8">
        <Outlet />
      </main>
      {/* The floating AI assistant for business owners and CAs (not admins). */}
      {(role === "business" || role === "ca") && <AssistantWidget role={role} />}
    </div>
  );
}
