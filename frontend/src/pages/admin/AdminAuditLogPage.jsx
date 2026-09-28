import { useState } from "react";

import { useAuditLog } from "@/api/admin";
import { errorMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/dates";

// What each recorded action means, in words.
const ACTION_LABELS = {
  "ca_profile.verify": "Verified a CA",
  "ca_profile.reject": "Rejected a CA",
  "user.suspend": "Suspended an account",
  "user.reactivate": "Reactivated an account",
};

// The details worth showing, e.g. "Reason: Fake documents · Requests cancelled: 2".
function detailsText(details) {
  if (!details) return "";
  const parts = [];
  if (details.reason) parts.push(`Reason: ${details.reason}`);
  if (details.cancelled_requests) parts.push(`Requests cancelled: ${details.cancelled_requests}`);
  return parts.join(" · ");
}

/** /admin/audit ("Audit log"): every admin action, newest first (AD8). */
export function AdminAuditLogPage() {
  const [page, setPage] = useState(1);
  const log = useAuditLog(page);
  const pages = log.isSuccess ? Math.max(1, Math.ceil(log.data.total / log.data.page_size)) : 1;

  return (
    <div className="max-w-5xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Audit log</h1>
        <p className="text-sm text-muted-foreground">
          Every admin action, newest first. Entries are never changed or deleted.
        </p>
      </div>
      {log.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {log.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(log.error)}
        </p>
      )}
      {log.isSuccess && log.data.items.length === 0 && (
        <p className="text-sm text-muted-foreground">No admin actions yet.</p>
      )}
      {log.isSuccess && log.data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b text-muted-foreground">
              <tr>
                <th className="py-2 pr-4 font-medium">When</th>
                <th className="py-2 pr-4 font-medium">Admin</th>
                <th className="py-2 pr-4 font-medium">Action</th>
                <th className="py-2 pr-4 font-medium">Who / what</th>
                <th className="py-2 font-medium">Details</th>
              </tr>
            </thead>
            <tbody>
              {log.data.items.map((entry) => (
                <tr key={entry.id} className="border-b align-top">
                  <td className="py-2 pr-4 whitespace-nowrap">
                    {formatDateTime(entry.created_at)}
                  </td>
                  <td className="py-2 pr-4">{entry.admin_name ?? "—"}</td>
                  <td className="py-2 pr-4">{ACTION_LABELS[entry.action] ?? entry.action}</td>
                  <td className="py-2 pr-4">{entry.target_name ?? entry.target_type}</td>
                  <td className="py-2">{detailsText(entry.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pages > 1 && (
        <div className="flex items-center gap-3 text-sm">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Previous
          </Button>
          <span>
            Page {page} of {pages}
          </span>
          <Button variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
