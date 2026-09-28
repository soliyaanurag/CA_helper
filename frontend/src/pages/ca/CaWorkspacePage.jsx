import { Link } from "react-router";

import { useCaClients } from "@/api/caWorkspace";
import { errorMessage } from "@/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { daysLeftText, formatDate } from "@/lib/dates";

/**
 * /ca/clients ("My clients"): the businesses the CA has active engagements with, most
 * urgent first. Each shows its urgency score and why it is flagged.
 */
export function CaWorkspacePage() {
  const clients = useCaClients();

  return (
    <div className="max-w-5xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">My clients</h1>
        <p className="text-sm text-muted-foreground">
          Businesses you are working for, most urgent first. Open a client to see their filings, ask
          for documents and mark filings as filed.
        </p>
      </div>
      {clients.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {clients.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(clients.error)}
        </p>
      )}
      {clients.isSuccess && clients.data.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No active clients yet. Accepted requests in{" "}
          <Link to="/ca/engagements" className="underline">
            My engagements
          </Link>{" "}
          appear here.
        </p>
      )}
      {clients.isSuccess &&
        clients.data.map((row) => <ClientCard key={row.business_id} row={row} />)}
    </div>
  );
}

function ClientCard({ row }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-3">
          <Link to={"/ca/clients/" + row.business_id} className="hover:underline">
            {row.business_name}
          </Link>
          <span
            className={
              "rounded-md px-2 py-0.5 text-sm tabular-nums " +
              (row.score > 0 ? "bg-red-100 text-red-800" : "bg-muted text-muted-foreground")
            }
          >
            Urgency {row.score}
          </span>
        </CardTitle>
        <CardDescription>
          {row.open_filing_count} of {row.filing_count} filings to do ·{" "}
          {row.next_deadline
            ? `next deadline ${formatDate(row.next_deadline)} (${daysLeftText(row.next_deadline).toLowerCase()})`
            : "no upcoming deadline"}{" "}
          · {row.overdue_count} overdue · {row.open_request_count} open document requests
        </CardDescription>
      </CardHeader>
      <CardContent className="text-sm">
        {row.reasons.length === 0 ? (
          <p className="text-muted-foreground">Nothing urgent.</p>
        ) : (
          <>
            <p className="font-medium">Why flagged</p>
            <ul className="list-disc pl-5">
              {row.reasons.map((reason) => (
                <li key={reason.reason}>
                  {reason.reason} <span className="text-muted-foreground">(+{reason.points})</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}
