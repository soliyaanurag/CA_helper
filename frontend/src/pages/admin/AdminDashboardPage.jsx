import { Link } from "react-router";

import { useAdminDashboard, useAdminStats } from "@/api/admin";
import { errorMessage } from "@/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { COMPLIANCE_STATUS_LABELS, label } from "@/lib/labels";

/** Admin home page: a welcome message and the counts that need an eye on them. */
export function AdminDashboardPage() {
  const dashboard = useAdminDashboard();
  const stats = useAdminStats();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">
        {dashboard.isPending
          ? "Loading..."
          : dashboard.isError
            ? "Dashboard"
            : dashboard.data.message}
      </h1>
      {dashboard.isError && (
        <Card>
          <CardHeader>
            <CardTitle>Could not load the dashboard</CardTitle>
            <CardDescription>{errorMessage(dashboard.error)}</CardDescription>
          </CardHeader>
        </Card>
      )}
      {stats.isSuccess && <Counts stats={stats.data} />}
      {stats.isSuccess && <Filings stats={stats.data} />}
    </div>
  );
}

function Counts({ stats }) {
  const cards = [
    ["Business users", stats.users_by_role.business],
    ["CAs", stats.users_by_role.ca],
    ["Admins", stats.users_by_role.admin],
    ["Businesses registered", stats.businesses],
    ["CAs pending verification", stats.cas_by_status.pending, "/admin/users"],
    ["Open engagements", stats.open_engagements],
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map(([title, value, link]) => (
        <Card key={title}>
          <CardHeader>
            <CardDescription>{title}</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{value}</CardTitle>
            {link && value > 0 && (
              <Link to={link} className="text-sm text-primary underline-offset-4 hover:underline">
                Review them
              </Link>
            )}
          </CardHeader>
        </Card>
      ))}
    </div>
  );
}

// Filings across all businesses by status, and how many due ones were late (AD5).
function Filings({ stats }) {
  const rate = stats.overdue_rate === null ? "No filing is due yet" : `${stats.overdue_rate}%`;
  return (
    <Card>
      <CardHeader>
        <CardDescription>Overdue rate</CardDescription>
        <CardTitle className="text-2xl tabular-nums">{rate}</CardTitle>
        <CardDescription>
          {stats.filings_late} of {stats.filings_due_so_far} filings due so far were not filed on
          time (still unfiled, or filed after the due date).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="mb-2 text-sm font-medium">Filings by status</p>
        <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(stats.filings_by_status).map(([status, count]) => (
            <div key={status} className="flex justify-between gap-2">
              <dt>{label(COMPLIANCE_STATUS_LABELS, status)}</dt>
              <dd className="tabular-nums">{count}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
