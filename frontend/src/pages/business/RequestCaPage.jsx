import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { errorMessage } from "@/api/client";
import {
  MY_ENGAGEMENTS_KEY,
  sendRequest,
  useRequestableFilings,
  useVerifiedCa,
} from "@/api/marketplace";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/dates";
import { FORM_LABELS, label } from "@/lib/labels";
import { formatRupees } from "@/lib/money";

// /business/marketplace/:caId/request: the business ticks the filings it wants this
// CA to do and sends the request. Filings that cannot be picked say why.
export function RequestCaPage() {
  const { caId } = useParams();
  const ca = useVerifiedCa(caId);
  const filings = useRequestableFilings(caId);

  let content;
  if (ca.isPending || filings.isPending) {
    content = <p className="text-sm text-muted-foreground">Loading...</p>;
  } else if (ca.isError || filings.isError) {
    content = (
      <p role="alert" className="text-sm text-destructive">
        {errorMessage(ca.error || filings.error)}
      </p>
    );
  } else if (filings.data === null) {
    content = (
      <p className="text-sm">
        <Link to="/business/onboarding" className="underline">
          Register your business
        </Link>{" "}
        first, so we know which filings you have.
      </p>
    );
  } else if (filings.data.length === 0) {
    content = <p className="text-sm">You have no filings due for the rest of this year.</p>;
  } else {
    content = <RequestForm caId={caId} filings={filings.data} />;
  }

  return (
    <div className="max-w-3xl space-y-6">
      <Link
        to={"/business/marketplace/" + caId}
        className="text-sm text-primary underline-offset-4 hover:underline"
      >
        ← Back to the CA
      </Link>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">
          Request {ca.isSuccess ? ca.data.full_name : "this CA"}
        </h1>
        <p className="text-sm text-muted-foreground">
          Tick the filings you want this CA to do. The CA can accept at these prices, send you a
          quote with new prices, or decline.
        </p>
      </div>
      {content}
    </div>
  );
}

// The price of the chosen service of one filing.
function priceOf(filing, serviceId) {
  for (const option of filing.options) {
    if (option.service_id === serviceId) {
      return Number(option.price);
    }
  }
  return 0;
}

function RequestForm({ caId, filings }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // { filing id: the chosen service id } for every ticked filing.
  const [chosen, setChosen] = useState({});
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);

  function toggle(filing) {
    const next = { ...chosen };
    if (next[filing.id]) {
      delete next[filing.id];
    } else {
      next[filing.id] = filing.options[0].service_id; // the first service by default
    }
    setChosen(next);
  }

  function chooseService(filing, serviceId) {
    setChosen({ ...chosen, [filing.id]: serviceId });
  }

  let total = 0;
  for (const filing of filings) {
    if (chosen[filing.id]) {
      total = total + priceOf(filing, chosen[filing.id]);
    }
  }
  const nothingTicked = Object.keys(chosen).length === 0;

  async function onSend() {
    setError(null);
    const items = [];
    for (const filing of filings) {
      if (chosen[filing.id]) {
        items.push({ compliance_item_id: filing.id, service_id: chosen[filing.id] });
      }
    }
    if (items.length === 0) {
      return; // the button is disabled until a filing is ticked
    }

    setSending(true);
    try {
      await sendRequest(caId, items);
      queryClient.invalidateQueries({ queryKey: MY_ENGAGEMENTS_KEY });
      queryClient.invalidateQueries({ queryKey: ["marketplace", "requestable-filings"] });
      navigate("/business/engagements", { state: { sent: true } });
    } catch (sendError) {
      setError(errorMessage(sendError));
      setSending(false);
    }
  }

  return (
    <div className="space-y-4">
      <ul className="space-y-2">
        {filings.map((filing) => (
          <li key={filing.id} className="rounded-lg border p-3 text-sm">
            <label htmlFor={"filing-" + filing.id} className="flex items-center gap-2 font-medium">
              <input
                id={"filing-" + filing.id}
                type="checkbox"
                value={filing.id}
                checked={Boolean(chosen[filing.id])}
                disabled={filing.blocked_reason !== null}
                onChange={() => toggle(filing)}
              />
              {label(FORM_LABELS, filing.form_code)} {filing.period_label}
              <span className="font-normal text-muted-foreground">
                · due {formatDate(filing.due_date)}
              </span>
            </label>
            {filing.blocked_reason ? (
              <p className="mt-1 text-muted-foreground">{filing.blocked_reason}</p>
            ) : (
              <FilingPrice
                filing={filing}
                serviceId={chosen[filing.id] || filing.options[0].service_id}
                onChoose={(serviceId) => chooseService(filing, serviceId)}
              />
            )}
          </li>
        ))}
      </ul>

      <p className="text-sm font-medium">Total at the listed prices: {formatRupees(total)}</p>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={onSend} disabled={sending || nothingTicked}>
          {sending ? "Sending..." : "Send request"}
        </Button>
        <p className="text-sm text-muted-foreground">
          {nothingTicked ? "Tick at least one filing. " : ""}The CA has 48 hours to respond.
        </p>
      </div>
    </div>
  );
}

// The CA's price for a filing. If the CA offers several services for it (ITR),
// the business picks one.
function FilingPrice({ filing, serviceId, onChoose }) {
  if (filing.options.length === 1) {
    const option = filing.options[0];
    return (
      <p className="mt-1">
        {option.name}: <span className="font-medium">{formatRupees(option.price)}</span>
      </p>
    );
  }
  return (
    <select
      aria-label={"Service for " + filing.period_label}
      className="mt-1 h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
      value={serviceId}
      onChange={(event) => onChoose(event.target.value)}
    >
      {filing.options.map((option) => (
        <option key={option.service_id} value={option.service_id}>
          {option.name}: {formatRupees(option.price)}
        </option>
      ))}
    </select>
  );
}
