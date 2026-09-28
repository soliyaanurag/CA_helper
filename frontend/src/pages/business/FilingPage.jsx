import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";

import { usePenaltyEstimate } from "@/api/alerts";
import { CA_WORKSPACE_KEY, fulfilDocumentRequest, useMyDocumentRequests } from "@/api/caWorkspace";
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
  usePeerInsights,
} from "@/api/compliance";
import {
  DOCUMENTS_KEY,
  UPLOAD_TYPES,
  downloadDocument,
  linkDocument,
  unlinkDocument,
  uploadDocument,
  useDocuments,
} from "@/api/documents";
import { useMyEngagements } from "@/api/marketplace";
import { FormField } from "@/components/FormField";
import { Markdown } from "@/components/Markdown";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { daysLeftText, daysUntil, formatDate, formatDateTime } from "@/lib/dates";
import {
  DOCUMENT_TYPE_LABELS,
  ENTITY_TYPE_LABELS,
  FORM_LABELS,
  MSME_TIER_LABELS,
  label,
} from "@/lib/labels";
import { formatRupees } from "@/lib/money";

// Statuses in which the business itself can still act on the filing.
const OPEN_FOR_BUSINESS = ["upcoming", "docs_pending", "ready", "overdue"];
const FILED = ["filed", "filed_verified"];
// Engagement statuses in which a CA request or CA work is still going on.
const OPEN_ENGAGEMENTS = ["requested", "quoted", "active"];
const SELECT_CLASS =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

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
          {!FILED.includes(filing.data.filing.status) &&
            daysUntil(filing.data.filing.due_date) < 0 && <Penalty item={filing.data.filing} />}
          <HowToFile page={filing.data} onUpdated={showUpdated} />
          <PeerInsights item={filing.data.filing} />
          <CaRequests page={filing.data} />
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

// --- What being late may cost (AL5) ------------------------------------------------------

// Shown on every penalty figure: the rules are not checked against official sources yet.
const PENDING_LABEL = "Estimate (rules pending verification)";

function Penalty({ item }) {
  const [taxDue, setTaxDue] = useState("");
  // The amount the estimate was last asked for (only on "Estimate", not on every key).
  const [askedTaxDue, setAskedTaxDue] = useState("");
  const estimate = usePenaltyEstimate(item.id, askedTaxDue, true);

  function onSubmit(event) {
    event.preventDefault();
    setAskedTaxDue(taxDue.trim());
  }

  return (
    <Card className="ring-red-300">
      <CardHeader>
        <CardTitle>Late fees and interest</CardTitle>
        <CardDescription>{estimate.data?.label ?? PENDING_LABEL}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {estimate.isPending && <p className="text-muted-foreground">Loading...</p>}
        {estimate.isError && (
          <p role="alert" className="text-destructive">
            {errorMessage(estimate.error)}
          </p>
        )}
        {estimate.isSuccess && <PenaltyFigures estimate={estimate.data} />}
        <form className="flex flex-wrap items-end gap-2" onSubmit={onSubmit}>
          <FormField
            id="tax_due"
            label="Tax due (₹, optional, for the interest)"
            inputMode="decimal"
            value={taxDue}
            onChange={(event) => setTaxDue(event.target.value)}
          />
          <Button type="submit" variant="outline">
            Estimate
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function PenaltyFigures({ estimate }) {
  const amount = (value) => (value === null ? "not available" : formatRupees(value));
  return (
    <div className="space-y-1">
      <p>{estimate.days_late} days late.</p>
      <p>Late fee: {amount(estimate.late_fee)}</p>
      <p>Interest: {amount(estimate.interest)}</p>
      {estimate.total !== null && (
        <p className="font-medium">Total: {formatRupees(estimate.total)}</p>
      )}
      {estimate.notes.map((note) => (
        <p key={note} className="text-muted-foreground">
          {note}
        </p>
      ))}
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

/**
 * DO8: what the acknowledgement file showed when it was read (locally, with OCR).
 * Verified: the form, period, number and date match this filing. Otherwise the list
 * says what did not match; the filing stays "Filed".
 */
function Verification({ verification }) {
  if (verification.verified) {
    return (
      <p className="rounded-lg bg-green-50 p-3 text-green-900">
        ✓ Verified from the acknowledgement: number {verification.acknowledgement_no}, filed on{" "}
        {formatDate(verification.filing_date)}.
      </p>
    );
  }
  return (
    <div className="rounded-lg bg-amber-50 p-3 text-amber-900">
      <p className="font-medium">We could not verify it from the acknowledgement:</p>
      <ul className="list-disc pl-5">
        {verification.problems.map((problem) => (
          <li key={problem}>{problem}</li>
        ))}
      </ul>
      <p className="mt-1 text-xs">
        Check that you uploaded the acknowledgement of this filing. It stays marked as filed.
      </p>
    </div>
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
        <CardTitle>{item.status === "filed_verified" ? "Filed and verified" : "Filed"}</CardTitle>
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
        {page.acknowledgement !== null && (
          <Verification verification={page.acknowledgement.verification} />
        )}
        {["filed", "filed_verified"].includes(item.status) && item.filing_path === "self" && (
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
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [busyKey, setBusyKey] = useState(null);
  const locked = FILED.includes(item.status);
  const documents = useDocuments({ compliance_item_id: item.id, page_size: 100 });
  const linked = linksByKey(documents.data, item.id);

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

  // A file was added or removed: the documents, and maybe a tick and the status, changed.
  function refresh() {
    queryClient.invalidateQueries({ queryKey: DOCUMENTS_KEY });
    queryClient.invalidateQueries({ queryKey: filingKey(item.id) });
    queryClient.invalidateQueries({ queryKey: FILINGS_KEY });
    queryClient.invalidateQueries({ queryKey: ["compliance", "dashboard"] });
  }

  const required = page.checklist.filter((entry) => entry.required);
  const requiredTicked = required.filter((entry) => entry.ticked);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Documents to have ready</CardTitle>
        <CardDescription>
          Tick what you have, or add the file: it is ticked for you, and a CA working on this filing
          can open it. {requiredTicked.length} of {required.length} required documents ready.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {page.checklist.map((entry) => (
          <div key={entry.key} className="space-y-1">
            <label className="flex items-start gap-2 text-sm">
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
            <EntryDocuments
              item={item}
              entryKey={entry.key}
              entryLabel={entry.label}
              links={linked[entry.key] ?? []}
              locked={locked}
              onChanged={refresh}
            />
          </div>
        ))}
        <div className="space-y-1 border-t pt-3">
          <p className="text-sm font-medium">Other documents for this filing</p>
          <EntryDocuments
            item={item}
            entryKey="general"
            entryLabel="this filing"
            links={linked.general ?? []}
            locked={locked}
            onChanged={refresh}
          />
        </div>
        {documents.isError && (
          <p role="alert" className="text-sm text-destructive">
            {errorMessage(documents.error)}
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// {checklist key: [{ link, document }]}: the files linked to this filing, per entry.
function linksByKey(documents, itemId) {
  const byKey = {};
  for (const document of documents?.items ?? []) {
    for (const link of document.links) {
      if (link.compliance_item_id !== itemId) continue;
      byKey[link.checklist_key] ??= [];
      byKey[link.checklist_key].push({ link, document });
    }
  }
  return byKey;
}

// The files linked to one checklist entry (or "general"), and "Add a file" for more.
function EntryDocuments({ item, entryKey, entryLabel, links, locked, onChanged }) {
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run(action) {
    setError(null);
    setBusy(true);
    try {
      await action();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  function remove(link) {
    run(async () => {
      await unlinkDocument(link.id);
      onChanged();
    });
  }

  return (
    <div className="ml-6 space-y-1 text-sm">
      {links.map(({ link, document }) => (
        <div key={link.id} className="flex flex-wrap items-center gap-x-2">
          <span className="break-all">{document.original_filename}</span>
          <Button
            variant="link"
            size="sm"
            disabled={busy}
            aria-label={"Open " + document.original_filename}
            onClick={() => run(() => downloadDocument(document))}
          >
            Open
          </Button>
          {!locked && (
            <Button
              variant="link"
              size="sm"
              disabled={busy}
              aria-label={"Remove " + document.original_filename}
              onClick={() => remove(link)}
            >
              Remove
            </Button>
          )}
        </div>
      ))}
      {!locked && !adding && (
        <Button
          variant="outline"
          size="sm"
          aria-label={"Add a file for " + entryLabel}
          onClick={() => setAdding(true)}
        >
          Add a file
        </Button>
      )}
      {adding && (
        <AddDocument
          item={item}
          entryKey={entryKey}
          links={links}
          onAdded={() => {
            setAdding(false);
            onChanged();
          }}
          onCancel={() => setAdding(false)}
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

// Upload a new file for the entry, or link one that is already in the vault.
function AddDocument({ item, entryKey, links, onAdded, onCancel }) {
  const vault = useDocuments({ page_size: 100 });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const alreadyLinked = new Set(links.map(({ document }) => document.id));
  const choices = (vault.data?.items ?? []).filter((document) => !alreadyLinked.has(document.id));

  async function run(action) {
    setError(null);
    setBusy(true);
    try {
      await action();
      onAdded();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  function onUpload(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = event.currentTarget.elements.file.files[0];
    if (!file) {
      setError("Choose a file to upload.");
      return;
    }
    run(() =>
      uploadDocument(file, {
        doc_type: form.get("doc_type"),
        compliance_item_id: item.id,
        checklist_key: entryKey,
      }),
    );
  }

  function onLink(event) {
    event.preventDefault();
    const documentId = new FormData(event.currentTarget).get("document_id");
    if (!documentId) {
      setError("Choose a file from your vault.");
      return;
    }
    run(() => linkDocument(documentId, item.id, entryKey));
  }

  return (
    <div className="space-y-3 rounded-lg border p-3">
      <form className="flex flex-wrap items-end gap-2" onSubmit={onUpload}>
        <div className="space-y-1">
          <Label htmlFor={"file-" + entryKey}>Upload a new file</Label>
          <Input id={"file-" + entryKey} name="file" type="file" accept=".pdf,.jpg,.jpeg,.png" />
        </div>
        <div className="space-y-1">
          <Label htmlFor={"type-" + entryKey}>Type</Label>
          <select
            id={"type-" + entryKey}
            name="doc_type"
            defaultValue="other"
            className={SELECT_CLASS}
          >
            {UPLOAD_TYPES.map((code) => (
              <option key={code} value={code}>
                {DOCUMENT_TYPE_LABELS[code]}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" size="sm" disabled={busy}>
          Upload
        </Button>
      </form>
      <form className="flex flex-wrap items-end gap-2" onSubmit={onLink}>
        <div className="space-y-1">
          <Label htmlFor={"existing-" + entryKey}>Or link one from your vault</Label>
          <select
            id={"existing-" + entryKey}
            name="document_id"
            defaultValue=""
            className={SELECT_CLASS}
          >
            <option value="">{vault.isPending ? "Loading..." : "Choose a file"}</option>
            {choices.map((document) => (
              <option key={document.id} value={document.id}>
                {document.original_filename} ({label(DOCUMENT_TYPE_LABELS, document.doc_type)})
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" size="sm" disabled={busy}>
          Link
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      </form>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

// --- How similar businesses file it (CO13) ----------------------------------------------

function PeerInsights({ item }) {
  const peers = usePeerInsights(item.id);
  if (!peers.isSuccess) return null;
  const data = peers.data;
  const form = label(FORM_LABELS, item.form_code);

  let who = `all ${data.business_count} businesses on CA Helper that filed ${form}`;
  if (data.scope === "segment") {
    const tier = label(MSME_TIER_LABELS, data.msme_tier).toLowerCase();
    const type = label(ENTITY_TYPE_LABELS, data.entity_type).toLowerCase();
    who = `${data.business_count} ${tier} businesses like yours (${type}) that filed ${form}`;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>How similar businesses file it</CardTitle>
        <CardDescription>
          {data.scope === "none"
            ? `Not enough businesses have filed ${form} here yet to compare (at least ${data.min_businesses} are needed).`
            : `Among ${who}:`}
        </CardDescription>
      </CardHeader>
      {data.scope !== "none" && (
        <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
          <PeerPath title="Filed it themselves" figures={data.self} />
          <PeerPath title="Filed it through a CA" figures={data.ca} />
        </CardContent>
      )}
    </Card>
  );
}

function PeerPath({ title, figures }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-muted-foreground">{title}</p>
      <p className="text-2xl font-semibold tabular-nums">{figures.share_pct ?? 0}%</p>
      <p>
        {figures.on_time_pct === null
          ? "No filings yet"
          : `${figures.on_time_pct}% of them on time`}
      </p>
    </div>
  );
}

// --- Documents the CA asked for (CW4) -------------------------------------------------

function CaRequests({ page }) {
  const item = page.filing;
  const requests = useMyDocumentRequests(item.id);
  const queryClient = useQueryClient();
  if (!requests.isSuccess || requests.data.length === 0) return null;

  const labels = { general: "A document" };
  for (const entry of page.checklist) labels[entry.key] = entry.label;

  // The request was answered: the file, the ticks and the to-dos changed.
  function refresh() {
    queryClient.invalidateQueries({ queryKey: CA_WORKSPACE_KEY });
    queryClient.invalidateQueries({ queryKey: DOCUMENTS_KEY });
    queryClient.invalidateQueries({ queryKey: filingKey(item.id) });
    queryClient.invalidateQueries({ queryKey: FILINGS_KEY });
  }

  return (
    <Card className="ring-amber-300">
      <CardHeader>
        <CardTitle>Your CA asked for documents</CardTitle>
        <CardDescription>Send each file here; your CA is told when it arrives.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {requests.data.map((request) => (
          <AnswerRequest
            key={request.id}
            request={request}
            what={label(labels, request.checklist_key)}
            onAnswered={refresh}
          />
        ))}
      </CardContent>
    </Card>
  );
}

// Answer one request with a new file (uploaded to the vault first) or a vault file.
function AnswerRequest({ request, what, onAnswered }) {
  const vault = useDocuments({ page_size: 100 });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const file = formElement.elements.file.files[0];
    const documentId = new FormData(formElement).get("document_id");
    if (!file && !documentId) {
      setError("Choose a file to upload, or one from your vault.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const chosen = file ? (await uploadDocument(file, { doc_type: "other" })).id : documentId;
      await fulfilDocumentRequest(request.id, chosen);
      onAnswered();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="space-y-2 rounded-lg border p-3" onSubmit={onSubmit}>
      <p>
        <span className="font-medium">{what}</span> · {request.ca_name}: “{request.message}”
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor={"answer-file-" + request.id}>Upload a file</Label>
          <Input
            id={"answer-file-" + request.id}
            name="file"
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor={"answer-vault-" + request.id}>or choose from your vault</Label>
          <select
            id={"answer-vault-" + request.id}
            name="document_id"
            defaultValue=""
            className={SELECT_CLASS}
          >
            <option value="">{vault.isPending ? "Loading..." : "Choose a file"}</option>
            {(vault.data?.items ?? []).map((document) => (
              <option key={document.id} value={document.id}>
                {document.original_filename}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" size="sm" disabled={busy}>
          Send to my CA
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
    </form>
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
