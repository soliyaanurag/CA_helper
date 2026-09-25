import { Card, CardDescription, CardHeader, CardTitle } from "@/core/components/ui/card";

import { useCaDashboard } from "../api";

/** CA home dashboard. For now a welcome message; clients and urgency scores come later. */
export function CaDashboardPage() {
  const dashboard = useCaDashboard();

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
            <CardDescription>{dashboard.error.message}</CardDescription>
          </CardHeader>
        </Card>
      )}
    </div>
  );
}
