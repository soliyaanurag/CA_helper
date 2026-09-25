import { Link } from "react-router";

import { useHealth } from "@/core/api/health";
import { Badge } from "@/core/components/ui/badge";
import { Card, CardDescription, CardHeader, CardTitle } from "@/core/components/ui/card";

const AREAS = [
  { to: "/app", title: "Business", text: "Profile, compliance calendar, documents, find a CA." },
  { to: "/ca", title: "Chartered Accountant", text: "Clients, deadlines and requests." },
  { to: "/admin", title: "Admin", text: "Users, CA verification and configuration." },
];

/** Landing page. For now it links to the three areas and shows API health. */
export function HomePage() {
  const health = useHealth();

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold">CA Helper</h1>
        <p className="text-muted-foreground">
          Know which filings apply to your business and when. File yourself or work with a fairly
          priced CA.
        </p>
        <p className="text-sm">
          API status:{" "}
          {health.isPending ? (
            <Badge variant="secondary">checking...</Badge>
          ) : health.isError ? (
            <Badge variant="destructive">unreachable</Badge>
          ) : (
            <Badge>
              {health.data.status} (database {health.data.database})
            </Badge>
          )}
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {AREAS.map((area) => (
          <Link key={area.to} to={area.to}>
            <Card className="h-full transition-colors hover:bg-muted/50">
              <CardHeader>
                <CardTitle>{area.title}</CardTitle>
                <CardDescription>{area.text}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
