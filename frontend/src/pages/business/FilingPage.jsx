import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";

import { errorMessage } from "@/api/client";
import {
  FILINGS_KEY,
  chooseFilingPath,
  filingKey,
  markFiled,
  tickChecklist,
  unmarkFiled,
  useAcknowledgementFile,
  useFiling,
} from "@/api/compliance";
import { useMyEngagements } from "@/api/marketplace";
import { FormField } from "@/components/FormField";
import { Markdown } from "@/components/Markdown";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { daysLeftText, formatDate, formatDateTime } from "@/lib/dates";
import { FORM_LABELS, label } from "@/lib/labels";

// Statuses in which the business itself can still act on the filing.
const OPEN_FOR_BUSINESS = ["upcoming", "docs_pending", "ready", "overdue"];
const FILED = ["filed", "filed_verified"];
// Engagement statuses in which a CA request or CA work is still going on.
const OPEN_ENGAGEMENTS = ["requested", "quoted", "active"];

/**
 * /business/compliance/:itemId: one filing. The business chooses how to file it
 * (itself or with a CA), ticks the documents it has, marks it filed with the
 * acknowledgement, and reads what the form is and how to file it.
 */
export function FilingPage() {
  const { itemId } = useParams();
  const filing = useFiling(itemId);
  const queryClient = useQueryClient();

  // Every action returns the updated filing: show it at once, and refresh the lists.
  function showUpdated(updated) {
    queryClient.setQueryData(filingKey(itemId), updated);
    queryClient.invalidateQueries({ queryKey: FILINGS_KEY });
    queryClient.invalidateQueries({ queryKey: ["compliance", "dashboard"] });
  }

  return (
    <div className="max-w-3xl space-y-6">
      <Link to="/business/compliance" className="text-sm text-muted-foreground hover:underline">
        ← Compliance calendar
      </Link>
      {filing.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {filing.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(filing.error)}
        </p>
      )}
      {filing.isSuccess && (
        <>
          <Header page={filing.data} />
          <HowToFile page={filing.data} onUpdated={showUpdated} />
          <Checklist page={filing.data} onUpdated={showUpdated} />
          <Guide page={filing.data} />
        </>
      )}
    </div>
  );
}

function Header({ page }) {
  const item = page.filing;
  return (
    <div className="space-y-1">
      <h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold">
        {label(FORM_LABELS, item.form_code)} · {item.period_label}
        <StatusBadge status={item.status} />
      </h1>
      <p className="text-sm text-muted-foreground">
        {page.form_name} · due {formatDate(item.due_date)}
        {!FILED.includes(item.status) && ` · ${daysLeftText(item.due_date)}`}
      </p>
    </div>
  );
}

// --- How the filing gets done: path, CA, mark filed (CO8, CO9) -------------------------

function HowToFile({ page, onUpdated }) {
  const item = page.filing;
  const engagements = useMyEngagements();
  // The CA engagement this filing is in, if any (a request, a quote or active work).
  const engagement = (engagements.data || []).find(
    (candidate) =>
      OPEN_ENGAGEMENTS.includes(candidate.status) &&
      candidate.items.some((engagementItem) => engagementItem.compliance_item_id === item.id),
  );

  if (FILED.includes(item.status)) {
    return <Filed page={page} onUpdated={onUpdated} />;
  }
  if (engagement || item.status === "with_ca") {
    let text = "A CA is working on this filing. They will mark it as filed.";
    if (engagement && engagement.status === "active") {
      text = `${engagement.ca_name} is working on this filing. They will mark it as filed.`;
    } else if (engagement) {
      text = `Your request to ${engagement.ca_name} is waiting for an answer.`;
    }
    return (
      <Card>
        <CardHeader>
          <CardTitle>With a CA</CardTitle>
          <CardDescription>
            {text}{" "}
            <Link to="/business/engagements" className="text-primary hover:underline">
              See my engagements
            </Link>
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }
  return <ChoosePath page={page} onUpdated={onUpdated} />;
}

function ChoosePath({ page, onUpdated }) {
  const item = page.filing;
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function choose(path) {
    setError(null);
    setBusy(true);
    try {
      onUpdated(await chooseFilingPath(item.id, path));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  // The marketplace can pre-select the matching service; ITR has several, so no filter.
  const findCaLink =
    item.form_code === "itr"
      ? "/business/marketplace"
      : `/business/marketplace?service=${item.form_code}`;

  return (
    <Card>
      <CardHeader>
        <CardTitle>How will you file it?</CardTitle>
        <CardDescription>
          File it yourself on the government portal, or let a CA do it for you.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {OPEN_FOR_BUSINESS.includes(item.status) && (
          <div className="flex flex-wrap gap-2">
            <Button
              variant={item.filing_path === "self" ? "default" : "outline"}
              aria-pressed={item.filing_path === "self"}
              disabled={busy}
              onClick={() => choose("self")}
            >
              I'll file it myself
            </Button>
            <Button
              variant={item.filing_path === "ca" ? "default" : "outline"}
              aria-pressed={item.filing_path === "ca"}
              disabled={busy}
              onClick={() => choose("ca")}
            >
              Get a CA
            </Button>
          </div>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {item.filing_path === "ca" && (
          <p className="text-sm">
            <Link to={findCaLink} className="text-primary hover:underline">
              Find a CA for this filing →
            </Link>
          </p>
        )}
        {item.filing_path === "self" && <MarkFiledForm page={page} onUpdated={onUpdated} />}
      </CardContent>
    </Card>
  );
}

function MarkFiledForm({ page, onUpdated }) {
  const [arn, setArn] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      onUpdated(await markFiled(page.filing.id, arn.trim(), file));
    } catch (failure) {
      setError(errorMessage(failure));
      setBusy(false);
    }
  }

  return (
    <form className="space-y-3 border-t pt-4" onSubmit={onSubmit}>
      <p className="text-sm font-medium">Filed it on the portal? Mark it as filed.</p>
      <FormField
        id="acknowledgement_no"
        label="Acknowledgement number / ARN (optional)"
        value={arn}
        onChange={(event) => setArn(event.target.value)}
      />
      <div className="space-y-2">
        <Label htmlFor="acknowledgement_file">
          Acknowledgement file (optional: PDF, JPG or PNG)
        </Label>
        <input
          id="acknowledgement_file"
          type="file"
          accept="application/pdf,image/jpeg,image/png"
          className="block text-sm"
          onChange={(event) => setFile(event.target.files[0] || null)}
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button type="submit" disabled={busy}>
        {busy ? "Saving..." : "Mark as filed"}
      </Button>
    </form>
  );
}

function Filed({ page, onUpdated }) {
  const item = page.filing;
  const [error, setError] = useState(null);
  const file = useAcknowledgementFile(item.id, page.acknowledgement !== null);
  // A local link to the downloaded file; freed again when the page closes.
  const url = useMemo(() => (file.data ? URL.createObjectURL(file.data) : null), [file.data]);
  useEffect(() => () => url && URL.revokeObjectURL(url), [url]);

  async function undo() {
    setError(null);
    try {
      onUpdated(await unmarkFiled(item.id));
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Filed</CardTitle>
        <CardDescription>
          {item.filed_at ? `Marked as filed on ${formatDateTime(item.filed_at)}.` : "Filed."}
          {item.acknowledgement_no && ` Acknowledgement number: ${item.acknowledgement_no}.`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {page.acknowledgement === null ? (
          <p className="text-muted-foreground">No acknowledgement file was uploaded.</p>
        ) : url ? (
          <a href={url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
            Open the acknowledgement ({page.acknowledgement.filename})
          </a>
        ) : (
          <p className="text-muted-foreground">Loading the acknowledgement...</p>
        )}
        {item.status === "filed" && item.filing_path === "self" && (
          <div>
            <Button variant="outline" size="sm" onClick={undo}>
              Undo: not filed yet
            </Button>
          </div>
        )}
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// --- Documents to have ready (CO7) ------------------------------------------------------

function Checklist({ page, onUpdated }) {
  const item = page.filing;
  const [error, setError] = useState(null);
  const [busyKey, setBusyKey] = useState(null);
  const locked = FILED.includes(item.status);

  async function toggle(entry) {
    setError(null);
    setBusyKey(entry.key);
    try {
      onUpdated(await tickChecklist(item.id, entry.key, !entry.ticked));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusyKey(null);
    }
  }

  const required = page.checklist.filter((entry) => entry.required);
  const requiredTicked = required.filter((entry) => entry.ticked);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Documents to have ready</CardTitle>
        <CardDescription>
          Tick what you have. {requiredTicked.length} of {required.length} required documents ready.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {page.checklist.map((entry) => (
          <label key={entry.key} className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              checked={entry.ticked}
              disabled={locked || busyKey !== null}
              onChange={() => toggle(entry)}
            />
            <span>
              {entry.label}
              {!entry.required && <span className="text-muted-foreground"> (if it applies)</span>}
              {entry.help && (
                <span className="block text-xs text-muted-foreground">{entry.help}</span>
              )}
            </span>
          </label>
        ))}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// --- What the form is and how to file it (CO6) -----------------------------------------

function Guide({ page }) {
  const [tab, setTab] = useState("instructions");
  const texts = {
    instructions: ["How to file it yourself", page.instructions],
    explanation: ["What is this form?", page.explanation],
  };

  return (
    <Card>
      <CardHeader>
        <div role="tablist" className="flex gap-2">
          {Object.entries(texts).map(([key, [title]]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={
                "rounded-full border px-3 py-1 text-sm " +
                (tab === key
                  ? "border-primary bg-primary text-primary-foreground"
                  : "hover:bg-muted")
              }
            >
              {title}
            </button>
          ))}
        </div>
        {page.content_status !== "DONE" && (
          <CardDescription>
            This guide is a draft that has not been checked yet. Follow the official portal when in
            doubt.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        <Markdown>{texts[tab][1]}</Markdown>
      </CardContent>
    </Card>
  );
}
