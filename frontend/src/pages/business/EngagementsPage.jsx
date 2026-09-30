import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation } from "react-router";

import {
  cancelProBonoRequest,
  engagementAction,
  errorMessage,
  FILINGS_KEY,
  joinProBonoQueue,
  MY_ENGAGEMENTS_KEY,
  PRO_BONO_KEY,
  useMyEngagements,
  useProBonoPage,
} from "@/api";
import { EngagementCard } from "@/components/shared";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui";
import { filingFormLabel, formatDate } from "@/lib";

// --- MyEngagementsPage -------------------------------------------------------------------------

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
        {engagement.status === "completed" && !engagement.rating && (
          <RateForm engagement={engagement} />
        )}
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

// MA17: rate the CA once the work is completed (1 to 5 stars and an optional review).
function RateForm({ engagement }) {
  const queryClient = useQueryClient();
  const [stars, setStars] = useState(0);
  const [review, setReview] = useState("");
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    if (stars === 0) {
      setError("Choose 1 to 5 stars.");
      return;
    }
    setError(null);
    setSending(true);
    try {
      await engagementAction(engagement.id, "rating", { stars: stars, review: review });
      queryClient.invalidateQueries({ queryKey: MY_ENGAGEMENTS_KEY });
    } catch (rateError) {
      setError(errorMessage(rateError));
    }
    setSending(false);
  }

  const choices = [1, 2, 3, 4, 5];
  return (
    <form className="w-full space-y-2 rounded-lg border p-3" onSubmit={onSubmit} noValidate>
      <p className="font-medium">Rate {engagement.ca_name}</p>
      <div className="flex gap-1">
        {choices.map((number) => (
          <button
            key={number}
            type="button"
            aria-label={number + (number === 1 ? " star" : " stars")}
            aria-pressed={stars === number}
            className="text-2xl text-amber-500"
            onClick={() => setStars(number)}
          >
            {number <= stars ? "★" : "☆"}
          </button>
        ))}
      </div>
      <textarea
        aria-label="Review (optional)"
        placeholder="How was working with this CA? (optional)"
        rows={2}
        maxLength={2000}
        className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm"
        value={review}
        onChange={(event) => setReview(event.target.value)}
      />
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      <Button type="submit" disabled={sending}>
        {sending ? "Sending..." : "Send rating"}
      </Button>
    </form>
  );
}

// --- ProBonoPage -------------------------------------------------------------------------------

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
              {filingFormLabel(filing.form_code, filing.period_label)} {filing.period_label} · due{" "}
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
              {filingFormLabel(filing.form_code, filing.period_label)} {filing.period_label}
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
