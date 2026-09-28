import { Link } from "react-router";

import { useCaBatches } from "@/api/caWorkspace";
import { errorMessage } from "@/api/client";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { daysLeftText, formatDate } from "@/lib/dates";
import { FORM_LABELS, label } from "@/lib/labels";

/**
 * /ca/batches ("Deadline batches"): every filing the CA still has to file, across
 * clients, grouped by form and due date, with each client's document readiness.
 */
export function CaBatchesPage() {
  const batches = useCaBatches();

  return (
    <div className="max-w-4xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Deadline batches</h1>
        <p className="text-sm text-muted-foreground">
          The same filing for several clients, due on the same day: see whose documents are ready.
        </p>
      </div>
      {batches.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {batches.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(batches.error)}
        </p>
      )}
      {batches.isSuccess && batches.data.length === 0 && (
        <p className="text-sm text-muted-foreground">No filings to do in your active work.</p>
      )}
      {batches.isSuccess &&
        batches.data.map((batch) => (
          <Card key={batch.form_code + batch.due_date}>
            <CardHeader>
              <CardTitle>
                {label(FORM_LABELS, batch.form_code)} · due {formatDate(batch.due_date)}
              </CardTitle>
              <CardDescription>
                {daysLeftText(batch.due_date)} · {batch.ready_count} of {batch.filings.length}{" "}
                clients have every required document
              </CardDescription>
            </CardHeader>
            <CardContent>
              <table className="w-full text-left text-sm">
                <thead className="border-b text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-4 font-medium">Client</th>
                    <th className="py-2 pr-4 font-medium">Period</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                    <th className="py-2 font-medium">Documents</th>
                  </tr>
                </thead>
                <tbody>
                  {batch.filings.map((row) => (
                    <tr key={row.compliance_item_id} className="border-b align-top">
                      <td className="py-2 pr-4">
                        <Link to={"/ca/clients/" + row.business_id} className="underline">
                          {row.business_name}
                        </Link>
                      </td>
                      <td className="py-2 pr-4">{row.period_label}</td>
                      <td className="py-2 pr-4">
                        <StatusBadge status={row.status} />
                      </td>
                      <td className="py-2">
                        {row.ready ? (
                          "Ready"
                        ) : (
                          <>
                            {row.required_ready} of {row.required_total} ready · missing:{" "}
                            {row.missing.join(", ")}
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        ))}
    </div>
  );
}
