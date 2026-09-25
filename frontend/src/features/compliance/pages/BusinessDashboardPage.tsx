import { Card, CardDescription, CardHeader, CardTitle } from "@/core/components/ui/card";

import { useComplianceDashboard } from "../api";

/** Business home dashboard. For now a welcome message; next deadline, due/overdue counts and the penalty estimator come later. */
export function BusinessDashboardPage() {
  const dashboard = useComplianceDashboard();

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
