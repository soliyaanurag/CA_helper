import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "@/api/client";
import {
  cancelProBonoRequest,
  joinProBonoQueue,
  PRO_BONO_KEY,
  useProBonoPage,
} from "@/api/marketplace";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/dates";
import { FORM_LABELS, label } from "@/lib/labels";

// /business/pro-bono: a micro business asks for a free (pro-bono) CA for some filings.
// A CA with free slots takes the request; it then appears in "My engagements".
export function ProBonoPage() {
  const page = useProBonoPage();

  let content;
  if (page.isPending) {
    content = <p className="text-sm text-muted-foreground">Loading...</p>;
  } else if (page.isError) {
    content = (
      <p role="alert" className="text-sm text-destructive">
        {errorMessage(page.error)}
      </p>
    );
  } else if (page.data === null) {
    content = (
      <p className="text-sm">
        <Link to="/business/onboarding" className="underline">
          Register your business
        </Link>{" "}
        first, so we know if you can get free help.
      </p>
    );
  } else if (page.data.request) {
    content = <QueuedRequest request={page.data.request} />;
  } else if (!page.data.eligible) {
    content = <p className="text-sm">{page.data.reason}</p>;
  } else {
    content = <JoinForm filings={page.data.filings} reason={page.data.reason} />;
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Pro-bono help</h1>
        <p className="text-sm text-muted-foreground">
          Some CAs give a few free engagements every month to micro enterprises.
        </p>
      </div>
      {content}
    </div>
  );
}

// The request waiting in the queue, with a button to leave it.
function QueuedRequest({ request }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function onCancel() {
    setError(null);
    setBusy(true);
    try {
      await cancelProBonoRequest(request.id);
      queryClient.invalidateQueries({ queryKey: PRO_BONO_KEY });
    } catch (cancelError) {
      setError(errorMessage(cancelError));
    }
    setBusy(false);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>You are in the queue</CardTitle>
        <CardDescription>
          A CA with a free slot will take your request. You will get an email, and the work will
          appear in "My engagements".
        </CardDescription>
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
        {request.note && <p>Your note: {request.note}</p>}
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
        <Button variant="outline" onClick={onCancel} disabled={busy}>
          Leave the queue
        </Button>
      </CardContent>
    </Card>
  );
}

// Tick the filings to get free help with, add a note, join the queue.
function JoinForm({ filings, reason }) {
  const queryClient = useQueryClient();
  // { filing id: true } for every ticked filing.
  const [chosen, setChosen] = useState({});
  const [note, setNote] = useState("");
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);

  function toggle(filingId) {
    setChosen({ ...chosen, [filingId]: !chosen[filingId] });
  }

  async function onSubmit(event) {
    event.preventDefault();
    const ids = [];
    for (const filing of filings) {
      if (chosen[filing.id]) {
        ids.push(filing.id);
      }
    }
    if (ids.length === 0) {
      setError("Tick at least one filing.");
      return;
    }
    setError(null);
    setSending(true);
    try {
      await joinProBonoQueue(ids, note);
      queryClient.invalidateQueries({ queryKey: PRO_BONO_KEY });
    } catch (joinError) {
      setError(errorMessage(joinError));
    }
    setSending(false);
  }

  return (
    <form className="space-y-4" onSubmit={onSubmit} noValidate>
      <p className="text-sm">{reason}</p>
      <ul className="space-y-2">
        {filings.map((filing) => (
          <li key={filing.id} className="rounded-lg border p-3 text-sm">
            <label className="flex items-center gap-2 font-medium">
              <input
                type="checkbox"
                checked={Boolean(chosen[filing.id])}
                disabled={filing.blocked_reason !== null}
                onChange={() => toggle(filing.id)}
              />
              {label(FORM_LABELS, filing.form_code)} {filing.period_label}
              <span className="font-normal text-muted-foreground">
                · due {formatDate(filing.due_date)}
              </span>
            </label>
            {filing.blocked_reason && (
              <p className="mt-1 text-muted-foreground">{filing.blocked_reason}</p>
            )}
          </li>
        ))}
      </ul>
      <textarea
        aria-label="Note for the CA (optional)"
        placeholder="Anything the CA should know? (optional)"
        rows={2}
        maxLength={1000}
        className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm"
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button type="submit" disabled={sending}>
        {sending ? "Sending..." : "Join the pro-bono queue"}
      </Button>
    </form>
  );
}
