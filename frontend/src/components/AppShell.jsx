import { Link, NavLink, Outlet } from "react-router";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { USER_ROLE_LABELS } from "@/lib/labels";
import { ROLE_HOME } from "@/lib/session";
import { cn } from "@/lib/utils";

/**
 * Layout for the logged-in areas (/business, /ca, /admin): sidebar with the
 * role's links, user name + logout, and the current page (<Outlet />).
 * `nav` is a list of { label, path } links (NAV in routes.jsx).
 */
export function AppShell({ role, nav }) {
  const { user, logout } = useAuth();
  const title = USER_ROLE_LABELS[role];
  const home = ROLE_HOME[role];

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="flex w-60 shrink-0 flex-col border-r bg-muted/40 p-4">
        <Link to={home} className="text-lg font-semibold">
          CA Helper
        </Link>
        <p className="text-xs text-muted-foreground">{title}</p>
        <nav className="mt-6 flex flex-col gap-1" aria-label={`${title} navigation`}>
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
        <div className="mt-auto space-y-2 border-t pt-4">
          <p className="truncate text-sm">{user?.full_name}</p>
          <Button variant="outline" size="sm" className="w-full" onClick={logout}>
            Log out
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-8">
        <Outlet />
      </main>
    </div>
  );
}
