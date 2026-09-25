import { Link } from "react-router";

import { Card, CardHeader, CardTitle } from "@/core/components/ui/card";
import type { NavItem } from "@/core/routing";

/** Default page of an area (/app, /ca, /admin): links to every section of that area. */
export function AreaIndexPage({ title, nav }: { title: string; nav: NavItem[] }) {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <div className="grid gap-4 md:grid-cols-3">
        {nav.map((item) => (
          <Link key={item.path} to={item.path}>
            <Card className="h-full transition-colors hover:bg-muted/50">
              <CardHeader>
                <CardTitle>{item.label}</CardTitle>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
