import { Link } from "react-router";

import { errorMessage } from "@/api/client";
import { useFilings } from "@/api/compliance";
import { Badge } from "@/components/ui/badge";
import { COMPLIANCE_STATUS_LABELS, FORM_LABELS, label } from "@/lib/labels";

// "2027-07-31" -> "31 Jul 2027". The date is built from its parts, so the
// browser's time zone cannot move it to the day before.
function formatDate(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * /business/compliance: every filing of the business, soonest due first.
 * The filings are created when the business registers (Business profile page).
 * A list for now; the month view comes later.
 */
export function CompliancePage() {
  const filings = useFilings();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Compliance calendar</h1>
      {filings.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {filings.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(filings.error)}
        </p>
      )}
      {filings.isSuccess && filings.data === null && (
        <p className="text-sm">
          <Link to="/business/onboarding" className="underline">
            Register your business
          </Link>{" "}
          to see which filings apply to you and when they are due.
        </p>
      )}
      {filings.isSuccess && filings.data !== null && filings.data.length === 0 && (
        <p className="text-sm text-muted-foreground">No filings due for the rest of this year.</p>
      )}
      {filings.isSuccess && filings.data !== null && filings.data.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead className="border-b text-muted-foreground">
            <tr>
              <th className="py-2 pr-4 font-medium">Form</th>
              <th className="py-2 pr-4 font-medium">Period</th>
              <th className="py-2 pr-4 font-medium">Due date</th>
              <th className="py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {filings.data.map((item) => (
              <tr key={item.id} className="border-b">
                <td className="py-2 pr-4">{label(FORM_LABELS, item.form_code)}</td>
                <td className="py-2 pr-4">{item.period_label}</td>
                <td className="py-2 pr-4">{formatDate(item.due_date)}</td>
                <td className="py-2">
                  <Badge variant="secondary">{label(COMPLIANCE_STATUS_LABELS, item.status)}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
