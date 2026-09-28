import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  CA_WORKSPACE_KEY,
  caMarkFiled,
  cancelDocumentRequest,
  createDocumentRequest,
  useCaClient,
} from "@/api/caWorkspace";
import { errorMessage } from "@/api/client";
import { downloadDocument } from "@/api/documents";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { daysLeftText, formatDate } from "@/lib/dates";
import {
  ENTITY_TYPE_LABELS,
  FORM_LABELS,
  GST_SCHEME_LABELS,
  ITR_FORM_LABELS,
  MSME_TIER_LABELS,
  label,
} from "@/lib/labels";
import { formatRupees } from "@/lib/money";

const SELECT_CLASS =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";
const FILED = ["filed", "filed_verified"];

/**
 * /ca/clients/:businessId: one client's workspace. The business profile, and the
 * filings of the CA's active engagements with their checklist, files, document
 * requests and "Mark as filed".
 */
export function CaClientPage() {
  const { businessId } = useParams();
  const client = useCaClient(businessId);
  const queryClient = useQueryClient();

  function refresh() {
    queryClient.invalidateQueries({ queryKey: CA_WORKSPACE_KEY });
  }

  return (
    <div className="max-w-4xl space-y-6">
      <Link to="/ca/clients" className="text-sm text-muted-foreground hover:underline">
        ← My clients
      </Link>
      {client.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {client.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(client.error)}
        </p>
      )}
      {client.isSuccess && (
        <>
          <h1 className="text-2xl font-semibold">{client.data.business.legal_name}</h1>
          <Profile business={client.data.business} profile={client.data.profile} />
          <h2 className="text-lg font-semibold">Filings you work on</h2>
          {client.data.filings.length === 0 && (
            <p className="text-sm text-muted-foreground">No filings in active work.</p>
          )}
          {client.data.filings.map((row) => (
            <FilingCard key={row.filing.id} businessId={businessId} row={row} onChanged={refresh} />
          ))}
        </>
      )}
    </div>
  );
}

function Profile({ business, profile }) {
  const lines = [
    ["Entity type", label(ENTITY_TYPE_LABELS, business.entity_type)],
    ["State", business.state],
    ["PAN", business.pan],
    ["GSTIN", business.gstin || "Not registered"],
    ["TAN", business.tan || "—"],
    ["Phone", business.phone],
    ["Annual turnover", formatRupees(business.annual_turnover)],
  ];
  if (profile) {
    lines.push(
      ["MSME tier", label(MSME_TIER_LABELS, profile.msme_tier)],
      ["GST scheme", label(GST_SCHEME_LABELS, profile.gst_scheme)],
      ["ITR form", label(ITR_FORM_LABELS, profile.itr_form)],
      ["Tax audit", profile.audit_applicable ? "Applies" : "Does not apply"],
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Business profile</CardTitle>
        <CardDescription>{business.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          {lines.map(([name, value]) => (
            <div key={name} className="flex gap-2">
              <dt className="text-muted-foreground">{name}:</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

function FilingCard({ businessId, row, onChanged }) {
  const item = row.filing;
  const filed = FILED.includes(item.status);
  const labels = { general: "Other", acknowledgement: "Acknowledgement" };
  for (const entry of row.checklist) labels[entry.key] = entry.label;
  const required = row.checklist.filter((entry) => entry.required);
  const ready = required.filter((entry) => entry.ticked);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-3">
          {label(FORM_LABELS, item.form_code)} · {item.period_label}
          <StatusBadge status={item.status} />
        </CardTitle>
        <CardDescription>
          Due {formatDate(item.due_date)}
          {!filed && ` · ${daysLeftText(item.due_date)}`}
          {item.acknowledgement_no && ` · Acknowledgement number ${item.acknowledgement_no}`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div>
          <p className="font-medium">
            Documents: {ready.length} of {required.length} required ready
          </p>
          <ul className="space-y-0.5">
            {row.checklist.map((entry) => (
              <li key={entry.key}>
                <span aria-hidden="true">{entry.ticked ? "✓" : "○"}</span> {entry.label}
                {!entry.required && <span className="text-muted-foreground"> (if it applies)</span>}
              </li>
            ))}
          </ul>
        </div>
        <Files files={row.documents} labels={labels} />
        <Requests requests={row.open_requests} labels={labels} onChanged={onChanged} />
        {!filed && (
          <RequestForm
            businessId={businessId}
            item={item}
            checklist={row.checklist}
            onChanged={onChanged}
          />
        )}
        {item.status === "with_ca" && (
          <MarkFiledForm businessId={businessId} item={item} onChanged={onChanged} />
        )}
      </CardContent>
    </Card>
  );
}

function Files({ files, labels }) {
  const [error, setError] = useState(null);

  async function open(file) {
    setError(null);
    try {
      await downloadDocument({ id: file.document_id, original_filename: file.original_filename });
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }

  return (
    <div>
      <p className="font-medium">Files</p>
      {files.length === 0 ? (
        <p className="text-muted-foreground">No files yet.</p>
      ) : (
        <ul>
          {files.map((file) => (
            <li
              key={file.document_id + file.checklist_key}
              className="flex flex-wrap items-center gap-2"
            >
              <span className="break-all">{file.original_filename}</span>
              <span className="text-muted-foreground">({label(labels, file.checklist_key)})</span>
              <Button
                variant="link"
                size="sm"
                aria-label={"Open " + file.original_filename}
                onClick={() => open(file)}
              >
                Open
              </Button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

function Requests({ requests, labels, onChanged }) {
  const [error, setError] = useState(null);

  async function cancel(request) {
    setError(null);
    try {
      await cancelDocumentRequest(request.id);
      onChanged();
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }

  if (requests.length === 0) return null;
  return (
    <div>
      <p className="font-medium">Waiting for the client</p>
      <ul>
        {requests.map((request) => (
          <li key={request.id} className="flex flex-wrap items-center gap-2">
            <span>
              {label(labels, request.checklist_key)}: {request.message}
            </span>
            <Button variant="link" size="sm" onClick={() => cancel(request)}>
              Cancel request
            </Button>
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

function RequestForm({ businessId, item, checklist, onChanged }) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setError(null);
    setSent(false);
    setBusy(true);
    try {
      await createDocumentRequest(
        businessId,
        item.id,
        form.get("checklist_key"),
        form.get("message").trim(),
      );
      formElement.reset();
      setSent(true);
      onChanged();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="space-y-2 rounded-lg border p-3" onSubmit={onSubmit}>
      <p className="font-medium">Ask for a document</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor={"key-" + item.id}>Document</Label>
          <select
            id={"key-" + item.id}
            name="checklist_key"
            defaultValue={checklist.find((entry) => !entry.ticked)?.key ?? "general"}
            className={SELECT_CLASS}
          >
            {checklist.map((entry) => (
              <option key={entry.key} value={entry.key}>
                {entry.label}
              </option>
            ))}
            <option value="general">Something else</option>
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor={"message-" + item.id}>Message</Label>
          <Input
            id={"message-" + item.id}
            name="message"
            required
            maxLength={1000}
            placeholder="What exactly you need"
          />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Button type="submit" size="sm" disabled={busy}>
          Send request
        </Button>
        {sent && <p className="text-muted-foreground">Sent. The client sees it as a to-do.</p>}
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
      </div>
    </form>
  );
}

function MarkFiledForm({ businessId, item, onChanged }) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  async function onSubmit(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setError(null);
    setBusy(true);
    try {
      const result = await caMarkFiled(
        businessId,
        item.id,
        form.get("acknowledgement_no").trim(),
        formElement.elements.file.files[0],
      );
      setDone(
        result.engagement_completed
          ? "Marked as filed. That was the last filing of the engagement, so it is now completed."
          : "Marked as filed.",
      );
      onChanged();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  if (done) return <p className="text-muted-foreground">{done}</p>;
  return (
    <form className="space-y-2 rounded-lg border p-3" onSubmit={onSubmit}>
      <p className="font-medium">Mark as filed</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor={"arn-" + item.id}>Acknowledgement number (ARN), optional</Label>
          <Input id={"arn-" + item.id} name="acknowledgement_no" maxLength={50} />
        </div>
        <div className="space-y-1">
          <Label htmlFor={"ack-" + item.id}>Acknowledgement file, optional</Label>
          <Input id={"ack-" + item.id} name="file" type="file" accept=".pdf,.jpg,.jpeg,.png" />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Button type="submit" size="sm" disabled={busy}>
          Mark as filed
        </Button>
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
      </div>
    </form>
  );
}
