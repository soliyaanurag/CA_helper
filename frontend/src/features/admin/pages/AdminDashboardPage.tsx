import { errorMessage } from "@/core/api/errors";
import { Card, CardDescription, CardHeader, CardTitle } from "@/core/components/ui/card";

import { useAdminDashboard } from "../api";

/** Admin home page. For now a welcome message; pending CA verifications and flagged news come later. */
export function AdminDashboardPage() {
  const dashboard = useAdminDashboard();

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
    </div>
  );
}
