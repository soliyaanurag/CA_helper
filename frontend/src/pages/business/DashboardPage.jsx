import { Link } from "react-router";

import {
  errorMessage,
  useComplianceDashboard,
  useFilings,
  useMyDocumentRequests,
  useMyEngagements,
  usePenaltyExposure,
} from "@/api";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui";
import { daysLeftText, daysUntil, filingFormLabel, formatDate, formatRupees } from "@/lib";

const DONE = ["filed", "filed_verified"];

/**
 * Business home: the welcome message, four numbers about the filings (next deadline,
 * due this month, overdue, with a CA; counted by GET /compliance/dashboard) and a short
 * to-do list made from the filings and engagements the other pages use.
 */
export function BusinessDashboardPage() {
  const dashboard = useComplianceDashboard();
  const filings = useFilings();
  const engagements = useMyEngagements();

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
      {filings.isSuccess && filings.data === null && (
        <p className="text-sm">
          <Link to="/business/onboarding" className="underline">
            Register your business
          </Link>{" "}
          to see your filings and deadlines here.
        </p>
      )}
      {dashboard.isSuccess && dashboard.data.registered && <Numbers numbers={dashboard.data} />}
      {dashboard.isSuccess && dashboard.data.registered && dashboard.data.overdue > 0 && (
        <PenaltyExposure />
      )}
      {filings.isSuccess && filings.data !== null && (
        <>
          <ToDo filings={filings.data} engagements={engagements.data || []} />
        </>
      )}
    </div>
  );
}

// The four cards; the counts come from the API (next_deadline, due_this_month, overdue, with_ca).
function Numbers({ numbers }) {
  const next = numbers.next_deadline;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <NumberCard
        title="Next deadline"
        value={next ? filingFormLabel(next.form_code, next.period_label) : "None"}
        note={
          next
            ? `${next.period_label} · ${formatDate(next.due_date)} · ${daysLeftText(next.due_date)}`
            : "Nothing due"
        }
      />
      <NumberCard title="Due this month" value={numbers.due_this_month} note="not filed yet" />
      <NumberCard
        title="Overdue"
        value={numbers.overdue}
        note={numbers.overdue ? "due date passed, not marked filed" : "all on time"}
        alert={numbers.overdue > 0}
      />
      <NumberCard title="With a CA" value={numbers.with_ca} note="a CA is working on them" />
    </div>
  );
}

// The late fees of the overdue filings (GET /alerts/penalties); interest is not included.
function PenaltyExposure() {
  const exposure = usePenaltyExposure(true);
  if (!exposure.isSuccess) {
    return null;
  }
  const data = exposure.data;
  let value = "Not available yet";
  if (data.estimated_count > 0) {
    value = formatRupees(data.total_late_fees);
  }
  let note = "late fees of your overdue filings (interest not included)";
  if (data.pending_count > 0) {
    note += `; ${data.pending_count} of ${data.overdue_count} have no confirmed rule yet`;
  }
  return (
    <Card className="ring-red-300">
      <CardHeader>
        <CardDescription>Penalty exposure · {data.label}</CardDescription>
        <CardTitle className="text-2xl text-red-700 tabular-nums">{value}</CardTitle>
        <p className="text-xs text-muted-foreground">{note}</p>
      </CardHeader>
    </Card>
  );
}

function NumberCard({ title, value, note, alert }) {
  return (
    <Card className={alert ? "ring-red-300" : undefined}>
      <CardHeader>
        <CardDescription>{title}</CardDescription>
        <CardTitle className={"text-2xl tabular-nums" + (alert ? " text-red-700" : "")}>
          {value}
        </CardTitle>
        <p className="text-xs text-muted-foreground">{note}</p>
      </CardHeader>
    </Card>
  );
}

function ToDo({ filings, engagements }) {
  const requests = useMyDocumentRequests();
  const tasks = [];
  // Documents a CA asked for (CW4), first: someone is waiting for them.
  for (const request of requests.data ?? []) {
    tasks.push({
      key: request.id,
      text: `${request.ca_name} asked for a document for ${filingFormLabel(request.form_code, request.period_label)} ${request.period_label}: ${request.message}`,
      to: `/business/compliance/${request.compliance_item_id}`,
    });
  }
  for (const engagement of engagements) {
    if (engagement.status === "quoted") {
      tasks.push({
        key: engagement.id,
        text: `${engagement.ca_name} sent a quote: accept or reject it`,
        to: "/business/engagements",
      });
    }
    if (engagement.status === "requested") {
      tasks.push({
        key: engagement.id,
        text: `Waiting for ${engagement.ca_name} to answer your request`,
        to: "/business/engagements",
      });
    }
  }
  const overdue = filings.filter(
    (item) => !DONE.includes(item.status) && daysUntil(item.due_date) < 0,
  );
  if (overdue.length > 0) {
    tasks.push({
      key: "overdue",
      text: `Check ${overdue.length} overdue filings`,
      to: "/business/compliance",
    });
  }
  // Filings due in the next 30 days with no way of filing chosen yet.
  const undecided = filings.filter(
    (item) =>
      item.filing_path === null &&
      item.status !== "with_ca" &&
      !DONE.includes(item.status) &&
      daysUntil(item.due_date) >= 0 &&
      daysUntil(item.due_date) <= 30,
  );
  for (const item of undecided.slice(0, 5)) {
    tasks.push({
      key: item.id,
      text: `Decide how to file ${filingFormLabel(item.form_code, item.period_label)} ${item.period_label} (${daysLeftText(item.due_date).toLowerCase()}): yourself or with a CA`,
      to: `/business/compliance/${item.id}`,
    });
  }

  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">To do</h2>
      {tasks.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing to do right now.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {tasks.map((task) => (
            <li key={task.key}>
              <Link to={task.to} className="underline-offset-4 hover:underline">
                {task.text}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
