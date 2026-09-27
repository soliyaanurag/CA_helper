import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage } from "@/api/client";
import { CA_ENGAGEMENTS_KEY, engagementAction, useCaEngagements } from "@/api/marketplace";
import { EngagementCard } from "@/components/EngagementCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FORM_LABELS, label } from "@/lib/labels";

// The groups on the page, in order, and which statuses belong to each.
const GROUPS = [
  { title: "New requests", statuses: ["requested"] },
  { title: "Active", statuses: ["active"] },
  { title: "Quote sent, waiting for the business", statuses: ["quoted"] },
  { title: "Finished", statuses: ["completed", "declined", "expired", "cancelled"] },
];

// The same limits as QuotePriceInputSchema in backend/app/schemas/marketplace.py.
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

  let buttons = null;
  if (engagement.status === "requested" && !quoting) {
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
            {label(FORM_LABELS, item.form_code)} {item.period_label}
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
