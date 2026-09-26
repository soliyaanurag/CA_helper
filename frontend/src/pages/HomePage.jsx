import { Link } from "react-router";

import { useHealth } from "@/api/health";
import { useAuth } from "@/hooks/useAuth";
import { ROLE_HOME } from "@/lib/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const AUDIENCES = [
  { title: "Businesses", text: "Profile, compliance calendar, documents, find a CA." },
  { title: "Chartered Accountants", text: "Clients, deadlines and requests." },
  { title: "Admins", text: "Users, CA verification and configuration." },
];

/** Landing page: what the platform is, log in / sign up buttons, and the API health badge. */
export function HomePage() {
  const health = useHealth();
  const { user } = useAuth();

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <h1 className="text-3xl font-semibold">CA Helper</h1>
        <p className="text-muted-foreground">
          Know which filings apply to your business and when. File yourself or work with a fairly
          priced CA.
        </p>
        {user ? (
          <Button asChild>
            <Link to={ROLE_HOME[user.role]}>Go to your dashboard</Link>
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button asChild>
              <Link to="/login">Log in</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/signup">Create an account</Link>
            </Button>
          </div>
        )}
        <p className="text-sm">
          API status:{" "}
          {health.isPending ? (
            <Badge variant="secondary">checking...</Badge>
          ) : health.isError ? (
            <Badge variant="destructive">unreachable</Badge>
          ) : health.data.status === "ok" ? (
            <Badge>ok</Badge>
          ) : (
            <Badge variant="destructive">API up, database {health.data.database}</Badge>
          )}
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {AUDIENCES.map((audience) => (
          <Card key={audience.title} className="h-full">
            <CardHeader>
              <CardTitle>{audience.title}</CardTitle>
              <CardDescription>{audience.text}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </div>
  );
}
