import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage } from "@/api/client";
import {
  NEWS_SOURCES_KEY,
  REGULATORY_CHANGES_KEY,
  addNewsSource,
  approveChange,
  rejectChange,
  scanNewsNow,
  setNewsSourceEnabled,
  useNewsSources,
  useRegulatoryChanges,
} from "@/api/regulatory";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate, formatDateTime } from "@/lib/dates";
import { ENTITY_TYPE_LABELS, FORM_LABELS, GST_SCHEME_LABELS, label } from "@/lib/labels";

const TABS = ["To review", "Reviewed", "Sources"];

const CHANGE_TYPE_LABELS = {
  due_date_extension: "Due date extension",
  rate_change: "Rate change",
  new_rule: "New rule",
  other: "Other",
};

/**
 * /admin/regulatory ("Regulatory news", RE4): changes found in the news wait here until an
 * admin approves them (then the affected businesses and their CAs are told) or rejects
 * them. The Sources tab lists the news sites and runs a scan now.
 */
export function RegulatoryAdminPage() {
  const [tab, setTab] = useState(TABS[0]);

  let content = <Sources />;
  if (tab === TABS[0]) {
    content = <Changes status="pending" />;
  } else if (tab === TABS[1]) {
    content = <Reviewed />;
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Regulatory news</h1>
        <p className="text-sm text-muted-foreground">
          Changes found in the news every morning. Nobody is told until you approve one.
        </p>
      </div>
      <div role="tablist" className="flex gap-2">
        {TABS.map((name) => (
          <Button
            key={name}
            role="tab"
            aria-selected={tab === name}
            variant={tab === name ? "default" : "outline"}
            size="sm"
            onClick={() => setTab(name)}
          >
            {name}
          </Button>
        ))}
      </div>
      {content}
    </div>
  );
}

function Reviewed() {
  return (
    <div className="space-y-6">
      <Changes status="approved" />
      <Changes status="rejected" />
    </div>
  );
}

// ----------------------------------------------------------------------------
// Changes
// ----------------------------------------------------------------------------

function Changes({ status }) {
  const changes = useRegulatoryChanges(status);

  if (changes.isPending) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }
  if (changes.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {errorMessage(changes.error)}
      </p>
    );
  }
  if (changes.data.length === 0) {
    let text = "Nothing waiting for review.";
    if (status === "approved") text = "No approved changes yet.";
    if (status === "rejected") text = "No rejected changes yet.";
    return <p className="text-sm text-muted-foreground">{text}</p>;
  }
  return (
    <div className="space-y-4">
      {changes.data.map((change) => (
        <ChangeCard key={change.id} change={change} />
      ))}
    </div>
  );
}

// "GSTR-3B, GSTR-1"
function formsText(formCodes) {
  const names = [];
  for (const code of formCodes) {
    names.push(label(FORM_LABELS, code));
  }
  return names.join(", ");
}

// Who the change is for, e.g. "GST scheme: Regular (QRMP) · States: Maharashtra".
function whoText(affected) {
  const parts = [];
  if (affected.gst_schemes) {
    const names = [];
    for (const code of affected.gst_schemes) names.push(label(GST_SCHEME_LABELS, code));
    parts.push("GST scheme: " + names.join(", "));
  }
  if (affected.entity_types) {
    const names = [];
    for (const code of affected.entity_types) names.push(label(ENTITY_TYPE_LABELS, code));
    parts.push("Business type: " + names.join(", "));
  }
  if (affected.states) {
    parts.push("States: " + affected.states.join(", "));
  }
  if (parts.length === 0) {
    return "Everyone with an open filing of these forms";
  }
  return parts.join(" · ");
}

function ChangeCard({ change }) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function decide(action) {
    setBusy(true);
    setError(null);
    try {
      if (action === "approve") {
        await approveChange(change.id);
      } else {
        await rejectChange(change.id);
      }
      queryClient.invalidateQueries({ queryKey: REGULATORY_CHANGES_KEY });
    } catch (problem) {
      setError(errorMessage(problem));
      setBusy(false);
    }
  }

  const dates = change.dates;
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{label(CHANGE_TYPE_LABELS, change.change_type)}</Badge>
          <Badge variant="secondary">{formsText(change.form_codes)}</Badge>
          {change.affected_categories.extracted_by === "keywords" && (
            <Badge variant="outline">Found by keywords (no AI): read the article</Badge>
          )}
        </div>
        <CardTitle className="pt-2 text-base">{change.summary}</CardTitle>
        <CardDescription>
          From{" "}
          <a href={change.article_url} target="_blank" rel="noreferrer" className="underline">
            {change.article_title}
          </a>{" "}
          ({change.source_name}
          {change.published_at ? ", " + formatDateTime(change.published_at) : ""})
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <dl className="grid gap-1 sm:grid-cols-[10rem_1fr]">
          <dt className="text-muted-foreground">For</dt>
          <dd>{whoText(change.affected_categories)}</dd>
          {dates.period && (
            <>
              <dt className="text-muted-foreground">Period</dt>
              <dd>{dates.period}</dd>
            </>
          )}
          {dates.old_due_date && (
            <>
              <dt className="text-muted-foreground">Old due date</dt>
              <dd>{formatDate(dates.old_due_date)}</dd>
            </>
          )}
          {dates.new_due_date && (
            <>
              <dt className="text-muted-foreground">New due date</dt>
              <dd>{formatDate(dates.new_due_date)}</dd>
            </>
          )}
          {change.status !== "pending" && (
            <>
              <dt className="text-muted-foreground">Reviewed</dt>
              <dd>
                {change.status === "approved" ? "Approved" : "Rejected"}{" "}
                {formatDateTime(change.reviewed_at)}
                {change.status === "approved" && ` · ${change.match_count} business(es) told`}
              </dd>
            </>
          )}
        </dl>
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
        {change.status === "pending" && (
          <div className="flex gap-2">
            <Button size="sm" disabled={busy} onClick={() => decide("approve")}>
              Approve and notify
            </Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={() => decide("reject")}>
              Reject
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ----------------------------------------------------------------------------
// Sources
// ----------------------------------------------------------------------------

const EMPTY_SOURCE = { name: "", url: "", kind: "rss" };

function Sources() {
  const queryClient = useQueryClient();
  const sources = useNewsSources();
  const [form, setForm] = useState(EMPTY_SOURCE);
  const [error, setError] = useState(null);
  const [scanResult, setScanResult] = useState(null);
  const [scanning, setScanning] = useState(false);

  async function onAdd(event) {
    event.preventDefault();
    setError(null);
    try {
      await addNewsSource(form);
      setForm(EMPTY_SOURCE);
      queryClient.invalidateQueries({ queryKey: NEWS_SOURCES_KEY });
    } catch (problem) {
      setError(errorMessage(problem));
    }
  }

  async function onToggle(source) {
    setError(null);
    try {
      await setNewsSourceEnabled(source.id, !source.enabled);
      queryClient.invalidateQueries({ queryKey: NEWS_SOURCES_KEY });
    } catch (problem) {
      setError(errorMessage(problem));
    }
  }

  async function onScan() {
    setError(null);
    setScanResult(null);
    setScanning(true);
    try {
      setScanResult(await scanNewsNow());
      queryClient.invalidateQueries({ queryKey: REGULATORY_CHANGES_KEY });
    } catch (problem) {
      setError(errorMessage(problem));
    }
    setScanning(false);
  }

  let rows = [];
  if (sources.data) {
    rows = sources.data;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>News sources</CardTitle>
          <CardDescription>
            Read every morning at 07:00. A site's robots.txt is checked first; a site that does not
            allow us is skipped.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {sources.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
          {rows.length > 0 && (
            <ul className="divide-y text-sm">
              {rows.map((source) => (
                <li key={source.id} className="flex items-center justify-between gap-4 py-2">
                  <span>
                    <span className="font-medium">{source.name}</span>{" "}
                    <span className="text-muted-foreground">
                      ({source.kind === "rss" ? "RSS feed" : "web page"})
                    </span>
                    <span className="block text-xs break-all text-muted-foreground">
                      {source.url}
                    </span>
                  </span>
                  <Button size="sm" variant="outline" onClick={() => onToggle(source)}>
                    {source.enabled ? "Switch off" : "Switch on"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex items-center gap-3">
            <Button size="sm" onClick={onScan} disabled={scanning}>
              {scanning ? "Scanning..." : "Scan now"}
            </Button>
            {scanResult && (
              <p role="status" className="text-sm">
                {scanResult.new_articles} new article(s), {scanResult.changes} change(s) to review
                {scanResult.blocked_by_robots > 0 &&
                  `, ${scanResult.blocked_by_robots} blocked by robots.txt`}
                {scanResult.failed > 0 && `, ${scanResult.failed} could not be read`}.
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Add a source</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-3 sm:grid-cols-2" onSubmit={onAdd}>
            <div className="space-y-2">
              <Label htmlFor="source-name">Name</Label>
              <Input
                id="source-name"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="source-kind">Kind</Label>
              <select
                id="source-kind"
                className="h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm"
                value={form.kind}
                onChange={(event) => setForm({ ...form, kind: event.target.value })}
              >
                <option value="rss">RSS feed</option>
                <option value="html">Web page (its links are read)</option>
              </select>
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="source-url">URL</Label>
              <Input
                id="source-url"
                placeholder="https://..."
                value={form.url}
                onChange={(event) => setForm({ ...form, url: event.target.value })}
              />
            </div>
            <div className="sm:col-span-2">
              <Button type="submit" size="sm" disabled={form.name === "" || form.url === ""}>
                Add source
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
