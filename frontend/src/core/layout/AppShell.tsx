import { Link, NavLink, Outlet } from "react-router";

import { cn } from "@/core/lib/utils";
import type { NavItem } from "@/core/routing";

interface AppShellProps {
  /** Area name shown under the logo, e.g. "Business". */
  title: string;
  nav: NavItem[];
}

/** Shared frame for the logged-in areas: sidebar navigation + page content. */
export function AppShell({ title, nav }: AppShellProps) {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="w-60 shrink-0 border-r bg-muted/40 p-4">
        <Link to="/" className="text-lg font-semibold">
          CA Helper
        </Link>
        <p className="text-xs text-muted-foreground">{title}</p>
        <nav className="mt-6 flex flex-col gap-1" aria-label={`${title} navigation`}>
          {nav.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
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
      </aside>
      <main className="flex-1 p-8">
        <Outlet />
      </main>
    </div>
  );
}
