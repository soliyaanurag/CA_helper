import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "@/api/client";
import {
  acceptProBonoRequest,
  CA_ENGAGEMENTS_KEY,
  PRO_BONO_QUEUE_KEY,
  useProBonoQueue,
} from "@/api/marketplace";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate, formatDateTime } from "@/lib/dates";
import { FORM_LABELS, label } from "@/lib/labels";

// /ca/pro-bono: micro businesses waiting for free help. A verified CA with free slots
// this month takes a request; it becomes an active engagement at ₹0.
export function CaProBonoPage() {
  const queue = useProBonoQueue();

  let content;
  if (queue.isPending) {
    content = <p className="text-sm text-muted-foreground">Loading...</p>;
  } else if (queue.isError) {
    content = (
      <p role="alert" className="text-sm text-destructive">
        {errorMessage(queue.error)}
      </p>
    );
  } else {
    content = <Queue data={queue.data} />;
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Pro-bono queue</h1>
        <p className="text-sm text-muted-foreground">
          Micro enterprises that asked for free help, oldest first.
        </p>
      </div>
      {content}
    </div>
  );
}

function Queue({ data }) {
  const slotsLeft = data.pledged - data.used_this_month;
  let canTake = true;
  let whyNot = null;
  if (!data.verified) {
    canTake = false;
    whyNot = "You can take requests once an admin has verified your profile.";
  } else if (data.pledged === 0) {
    canTake = false;
    whyNot = "Set your free (pro-bono) slots per month on My profile to take requests.";
  } else if (slotsLeft <= 0) {
    canTake = false;
    whyNot = "You have used all your free slots this month.";
  }

  return (
    <div className="space-y-4">
      <p className="text-sm">
        Free slots this month: <b>{Math.max(slotsLeft, 0)}</b> of {data.pledged}.{" "}
        <Link to="/ca/profile" className="text-primary underline-offset-4 hover:underline">
          Change on My profile
        </Link>
      </p>
      {whyNot && <p className="text-sm text-muted-foreground">{whyNot}</p>}
      {data.requests.length === 0 ? (
        <p className="text-sm">Nobody is waiting right now.</p>
      ) : (
        <ul className="space-y-3">
          {data.requests.map((request) => (
            <li key={request.id}>
              <RequestCard request={request} canTake={canTake} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RequestCard({ request, canTake }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function onTake() {
    setError(null);
    setBusy(true);
    try {
      await acceptProBonoRequest(request.id);
      queryClient.invalidateQueries({ queryKey: PRO_BONO_QUEUE_KEY });
      queryClient.invalidateQueries({ queryKey: CA_ENGAGEMENTS_KEY });
    } catch (takeError) {
      setError(errorMessage(takeError));
    }
    setBusy(false);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{request.business_name}</CardTitle>
        <CardDescription>Waiting since {formatDateTime(request.created_at)}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <ul className="list-disc pl-5">
          {request.filings.map((filing) => (
            <li key={filing.id}>
              {label(FORM_LABELS, filing.form_code)} {filing.period_label} · due{" "}
              {formatDate(filing.due_date)}
            </li>
          ))}
        </ul>
        {request.note && <p>Note: {request.note}</p>}
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
        <Button onClick={onTake} disabled={!canTake || busy}>
          {busy ? "Taking..." : "Take this request (free)"}
        </Button>
      </CardContent>
    </Card>
  );
}
