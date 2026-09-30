import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import {
  acceptProBonoRequest,
  CA_ENGAGEMENTS_KEY,
  engagementAction,
  errorMessage,
  PRO_BONO_QUEUE_KEY,
  useCaEngagements,
  useProBonoQueue,
} from "@/api";
import { EngagementCard } from "@/components/shared";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
} from "@/components/ui";
import { filingFormLabel, formatDate, formatDateTime, isPast } from "@/lib";

// --- CaEngagementsPage -------------------------------------------------------------------------

// The groups on the page, in order, and which statuses belong to each.
const GROUPS = [
  { title: "New requests", statuses: ["requested"] },
  { title: "Active", statuses: ["active"] },
  { title: "Quote sent, waiting for the business", statuses: ["quoted"] },
  { title: "Finished", statuses: ["completed", "declined", "expired", "cancelled"] },
];

// The same limits as the checks in backend/app/marketplace.py.
const MAX_PRICE = 1000000;

// /ca/engagements: every request businesses sent to this CA, grouped by status, with
// the CA's actions (accept, send a quote, decline, mark as completed).
export function CaEngagementsPage() {
  const engagements = useCaEngagements();

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">My engagements</h1>
      {engagements.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {engagements.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(engagements.error)}
        </p>
      )}
      {engagements.isSuccess && engagements.data.length === 0 && (
        <p className="text-sm">
          No requests yet. Businesses can find you in the marketplace once your profile is verified.
        </p>
      )}
      {engagements.isSuccess &&
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
                  title={engagement.business_name}
                >
                  <CaActions engagement={engagement} />
                </EngagementCard>
              ))}
            </section>
          );
        })}
    </div>
  );
}

// The buttons the CA has for one engagement.
function CaActions({ engagement }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [quoting, setQuoting] = useState(false);

  async function run(action, body) {
    setError(null);
    setBusy(true);
    try {
      await engagementAction(engagement.id, action, body);
      queryClient.invalidateQueries({ queryKey: CA_ENGAGEMENTS_KEY });
      setQuoting(false);
    } catch (actionError) {
      setError(errorMessage(actionError));
    }
    setBusy(false);
  }

  // After 48 hours the CA can no longer answer; the worker will close the request.
  const answerTimeOver =
    engagement.status === "requested" && engagement.expires_at && isPast(engagement.expires_at);

  let buttons = null;
  if (answerTimeOver) {
    buttons = (
      <p className="text-muted-foreground">
        The 48 hours to answer are over. This request will close automatically.
      </p>
    );
  } else if (engagement.status === "requested" && !quoting) {
    buttons = (
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => run("accept")} disabled={busy}>
          Accept at listed prices
        </Button>
        <Button variant="outline" onClick={() => setQuoting(true)} disabled={busy}>
          Send a quote
        </Button>
        <Button variant="outline" onClick={() => run("decline")} disabled={busy}>
          Decline
        </Button>
      </div>
    );
  } else if (engagement.status === "active") {
    buttons = (
      <Button onClick={() => run("complete")} disabled={busy}>
        Mark as completed
      </Button>
    );
  }

  return (
    <div className="space-y-2">
      {buttons}
      {quoting && (
        <QuoteForm
          engagement={engagement}
          busy={busy}
          onSend={(body) => run("quote", body)}
          onCancel={() => setQuoting(false)}
        />
      )}
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

// A new price for every filing (starting from the listed price) and a reason.
function QuoteForm({ engagement, busy, onSend, onCancel }) {
  const startingPrices = {};
  for (const item of engagement.items) {
    startingPrices[item.id] = String(Number(item.listed_price)); // "800.00" -> "800"
  }
  const [prices, setPrices] = useState(startingPrices);
  const [reason, setReason] = useState("");
  const [formError, setFormError] = useState(null);

  function onSubmit(event) {
    event.preventDefault();
    const body = { reason: reason.trim(), prices: [] };
    for (const item of engagement.items) {
      const price = Number(prices[item.id]);
      if (prices[item.id] === "" || isNaN(price) || price < 0 || price > MAX_PRICE) {
        setFormError("Enter a price from 0 to 10,00,000 for every filing.");
        return;
      }
      body.prices.push({ engagement_item_id: item.id, price: prices[item.id] });
    }
    if (body.reason === "") {
      setFormError("Tell the business why the price is different.");
      return;
    }
    setFormError(null);
    onSend(body);
  }

  return (
    <form className="space-y-3 rounded-lg border p-3" onSubmit={onSubmit} noValidate>
      <p className="font-medium">Your quote</p>
      {engagement.items.map((item) => (
        <div key={item.id} className="flex flex-wrap items-center gap-2">
          <Label htmlFor={"quote-" + item.id} className="w-56">
            {filingFormLabel(item.form_code, item.period_label)} {item.period_label}
          </Label>
          <span>₹</span>
          <Input
            id={"quote-" + item.id}
            inputMode="decimal"
            className="w-32"
            value={prices[item.id]}
            onChange={(event) => setPrices({ ...prices, [item.id]: event.target.value })}
          />
        </div>
      ))}
      <div className="space-y-1">
        <Label htmlFor={"reason-" + engagement.id}>Reason (the business sees it)</Label>
        <textarea
          id={"reason-" + engagement.id}
          rows={2}
          className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </div>
      {formError && <p className="text-destructive">{formError}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={busy}>
          Send quote
        </Button>
        <Button type="button" variant="outline" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

// --- CaProBonoPage -----------------------------------------------------------------------------

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
              {filingFormLabel(filing.form_code, filing.period_label)} {filing.period_label} · due{" "}
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
