import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation } from "react-router";

import { errorMessage } from "@/api/client";
import { FILINGS_KEY } from "@/api/compliance";
import { engagementAction, MY_ENGAGEMENTS_KEY, useMyEngagements } from "@/api/marketplace";
import { EngagementCard } from "@/components/EngagementCard";
import { Button } from "@/components/ui/button";

// The groups on the page, in order, and which statuses belong to each.
const GROUPS = [
  { title: "Quote to review", statuses: ["quoted"] },
  { title: "Waiting for the CA", statuses: ["requested"] },
  { title: "Active", statuses: ["active"] },
  { title: "Finished", statuses: ["completed", "declined", "expired", "cancelled"] },
];

// /business/engagements: every request the business sent to a CA, grouped by status,
// with the actions it can take (accept or reject a quote, withdraw a request).
export function MyEngagementsPage() {
  const location = useLocation();
  const engagements = useMyEngagements();
  const justSent = location.state && location.state.sent;

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">My engagements</h1>
      {justSent && (
        <p role="status" className="text-sm font-medium text-green-700">
          Your request was sent. The CA has been emailed.
        </p>
      )}
      {engagements.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {engagements.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(engagements.error)}
        </p>
      )}
      {engagements.isSuccess && engagements.data === null && (
        <p className="text-sm">
          <Link to="/business/onboarding" className="underline">
            Register your business
          </Link>{" "}
          first, then request a CA from "Find a CA".
        </p>
      )}
      {engagements.isSuccess && engagements.data !== null && engagements.data.length === 0 && (
        <p className="text-sm">
          You have not requested a CA yet.{" "}
          <Link to="/business/marketplace" className="underline">
            Find a CA
          </Link>
        </p>
      )}
      {engagements.isSuccess &&
        engagements.data !== null &&
        GROUPS.map((group) => {
          const inGroup = engagements.data.filter((engagement) =>
            group.statuses.includes(engagement.status),
          );
          if (inGroup.length === 0) {
            return null;
          }
          return (
            <section key={group.title} className="space-y-3">
              <h2 className="text-lg font-semibold">{group.title}</h2>
              {inGroup.map((engagement) => (
                <EngagementCard
                  key={engagement.id}
                  engagement={engagement}
                  title={engagement.ca_name}
                >
                  <BusinessActions engagement={engagement} />
                </EngagementCard>
              ))}
            </section>
          );
        })}
    </div>
  );
}

// The buttons the business has for one engagement: accept or reject a quote,
// or withdraw a request the CA has not answered.
function BusinessActions({ engagement }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run(action) {
    setError(null);
    setBusy(true);
    try {
      await engagementAction(engagement.id, action);
      queryClient.invalidateQueries({ queryKey: MY_ENGAGEMENTS_KEY });
      queryClient.invalidateQueries({ queryKey: FILINGS_KEY }); // filings may now be "With CA"
    } catch (actionError) {
      setError(errorMessage(actionError));
    }
    setBusy(false);
  }

  let buttons = null;
  if (engagement.status === "quoted") {
    buttons = (
      <>
        <Button onClick={() => run("accept-quote")} disabled={busy}>
          Accept quote
        </Button>
        <Button variant="outline" onClick={() => run("reject-quote")} disabled={busy}>
          Reject quote
        </Button>
      </>
    );
  } else if (engagement.status === "requested") {
    buttons = (
      <Button variant="outline" onClick={() => run("withdraw")} disabled={busy}>
        Withdraw request
      </Button>
    );
  } else if (engagement.status === "expired" || engagement.status === "declined") {
    // The CA did not take it: the filings are free, so offer to pick another CA.
    buttons = (
      <Button asChild>
        <Link to="/business/marketplace">Find another CA</Link>
      </Button>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {buttons}
        <Link
          to={"/business/marketplace/" + engagement.ca_profile_id}
          className="self-center text-primary underline-offset-4 hover:underline"
        >
          View CA
        </Link>
      </div>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
