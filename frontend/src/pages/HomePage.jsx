import { Link } from "react-router";

import { useHealth } from "@/api/health";
import { useAuth } from "@/hooks/useAuth";
import { ROLE_HOME } from "@/lib/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// Each card links to where that audience starts: signup with the role chosen, or login.
const AUDIENCES = [
  {
    title: "Businesses",
    text: "Profile, compliance calendar, documents, find a CA.",
    action: "Create a business account",
    to: "/signup",
    state: { role: "business" },
  },
  {
    title: "Chartered Accountants",
    text: "Clients, deadlines and requests.",
    action: "Join as a CA",
    to: "/signup",
    state: { role: "ca" },
  },
  {
    title: "Admins",
    text: "Users, CA verification and configuration.",
    action: "Log in",
    to: "/login",
  },
];

/** The API status badge is for developers: shown in development, or when something is down. */
function showApiStatus(health) {
  if (import.meta.env.DEV || health.isError) return true;
  return health.isSuccess && health.data.status !== "ok";
}

/** Landing page: what the platform is, log in / sign up buttons, and (see above) API status. */
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
        {showApiStatus(health) && (
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
        )}
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {AUDIENCES.map((audience) => (
          <Link
            key={audience.title}
            to={audience.to}
            state={audience.state}
            className="rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            <Card className="h-full transition-colors hover:bg-muted/50">
              <CardHeader>
                <CardTitle>{audience.title}</CardTitle>
                <CardDescription>{audience.text}</CardDescription>
                <span className="text-sm font-medium text-primary">{audience.action} →</span>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
