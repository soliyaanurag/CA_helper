import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import {
  deleteDocument,
  DOCUMENTS_KEY,
  downloadDocument,
  errorMessage,
  UPLOAD_TYPES,
  uploadDocument,
  useDocuments,
  useFilings,
} from "@/api";
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
import { DOCUMENT_TYPE_LABELS, filingFormLabel, formatDateTime, label, todayIso } from "@/lib";

const SELECT_CLASS =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

const PAGE_SIZE = 20;

// This financial year and the three before it, e.g. ["2026-27", "2025-26", ...].
// A financial year runs from April to March.
function recentFinancialYears() {
  const [year, month] = todayIso().split("-").map(Number);
  const start = month >= 4 ? year : year - 1;
  const years = [];
  for (let first = start; first > start - 4; first--) {
    years.push(`${first}-${String((first + 1) % 100).padStart(2, "0")}`);
  }
  return years;
}

// "240 KB", "1.5 MB".
function formatSize(bytes) {
  if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

// "GSTR-1 · Q2 2026-27"
function filingName(filing) {
  return `${filingFormLabel(filing.form_code, filing.period_label)} · ${filing.period_label}`;
}

/**
 * /business/documents: the document vault. Upload files, filter them by financial
 * year, type and filing, open them and delete them. Files are stored encrypted.
 */
export function DocumentsPage() {
  const [filters, setFilters] = useState({ fy: "", doc_type: "", compliance_item_id: "" });
  const [page, setPage] = useState(1);
  const documents = useDocuments({ ...filters, page, page_size: PAGE_SIZE });

  function changeFilter(name, value) {
    setFilters({ ...filters, [name]: value });
    setPage(1);
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Document vault</h1>
        <p className="text-sm text-muted-foreground">
          Your documents, stored encrypted. Link them to a filing from its page, so your CA can see
          them while working on it.
        </p>
      </div>
      <UploadCard />
      <Card>
        <CardHeader>
          <CardTitle>Your documents</CardTitle>
          <CardDescription>
            {documents.isSuccess && `${documents.data.total} documents`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Filters filters={filters} onChange={changeFilter} />
          {documents.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
          {documents.isError && (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage(documents.error)}
            </p>
          )}
          {documents.isSuccess && (
            <DocumentTable result={documents.data} page={page} onPage={setPage} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function UploadCard() {
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const file = formElement.elements.file.files[0];
    setError(null);
    setDone(null);
    if (!file) {
      setError("Choose a file to upload.");
      return;
    }
    setBusy(true);
    try {
      const document = await uploadDocument(file, {
        doc_type: form.get("doc_type"),
        fy: form.get("fy"),
        period_label: form.get("period_label").trim(),
      });
      setDone(`Uploaded ${document.original_filename}.`);
      formElement.reset();
      queryClient.invalidateQueries({ queryKey: DOCUMENTS_KEY });
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload a document</CardTitle>
        <CardDescription>PDF, JPG or PNG.</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="grid gap-3 sm:grid-cols-2 sm:items-end lg:grid-cols-4" onSubmit={onSubmit}>
          <div className="space-y-2">
            <Label htmlFor="upload_file">File</Label>
            <Input id="upload_file" name="file" type="file" accept=".pdf,.jpg,.jpeg,.png" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="upload_type">Type</Label>
            <select id="upload_type" name="doc_type" defaultValue="other" className={SELECT_CLASS}>
              {UPLOAD_TYPES.map((code) => (
                <option key={code} value={code}>
                  {DOCUMENT_TYPE_LABELS[code]}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="upload_fy">Financial year</Label>
            <select id="upload_fy" name="fy" defaultValue="" className={SELECT_CLASS}>
              <option value="">Not set</option>
              {recentFinancialYears().map((fy) => (
                <option key={fy} value={fy}>
                  {fy}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="upload_period">Period (optional)</Label>
            <Input
              id="upload_period"
              name="period_label"
              placeholder="e.g. Apr 2026"
              maxLength={30}
            />
          </div>
          <div className="flex items-center gap-3 sm:col-span-2 lg:col-span-4">
            <Button type="submit" disabled={busy}>
              {busy ? "Uploading..." : "Upload"}
            </Button>
            {done && <p className="text-sm text-muted-foreground">{done}</p>}
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function Filters({ filters, onChange }) {
  const filings = useFilings();

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="space-y-2">
        <Label htmlFor="filter_fy">Financial year</Label>
        <select
          id="filter_fy"
          value={filters.fy}
          onChange={(event) => onChange("fy", event.target.value)}
          className={SELECT_CLASS}
        >
          <option value="">Any</option>
          {recentFinancialYears().map((fy) => (
            <option key={fy} value={fy}>
              {fy}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="filter_type">Type</Label>
        <select
          id="filter_type"
          value={filters.doc_type}
          onChange={(event) => onChange("doc_type", event.target.value)}
          className={SELECT_CLASS}
        >
          <option value="">Any</option>
          {Object.entries(DOCUMENT_TYPE_LABELS).map(([code, text]) => (
            <option key={code} value={code}>
              {text}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="filter_filing">Filing</Label>
        <select
          id="filter_filing"
          value={filters.compliance_item_id}
          onChange={(event) => onChange("compliance_item_id", event.target.value)}
          className={SELECT_CLASS}
        >
          <option value="">Any</option>
          {filings.isSuccess &&
            (filings.data ?? []).map((filing) => (
              <option key={filing.id} value={filing.id}>
                {filingName(filing)}
              </option>
            ))}
        </select>
      </div>
    </div>
  );
}

function DocumentTable({ result, page, onPage }) {
  const pages = Math.max(1, Math.ceil(result.total / PAGE_SIZE));

  if (result.items.length === 0) {
    return <p className="text-sm text-muted-foreground">No documents here yet.</p>;
  }
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b text-muted-foreground">
            <tr>
              <th className="py-2 pr-4 font-medium">File</th>
              <th className="py-2 pr-4 font-medium">Type</th>
              <th className="py-2 pr-4 font-medium">Year / period</th>
              <th className="py-2 pr-4 font-medium">Size</th>
              <th className="py-2 pr-4 font-medium">Uploaded</th>
              <th className="py-2 pr-4 font-medium">Used for</th>
              <th className="py-2 font-medium">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {result.items.map((document) => (
              <DocumentRow key={document.id} document={document} />
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center gap-3 text-sm">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
            Previous
          </Button>
          <span>
            Page {page} of {pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pages}
            onClick={() => onPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}

function DocumentRow({ document }) {
  const queryClient = useQueryClient();
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

  function onDelete() {
    if (!window.confirm(`Delete ${document.original_filename}?`)) return;
    run(async () => {
      await deleteDocument(document.id);
      queryClient.invalidateQueries({ queryKey: DOCUMENTS_KEY });
    });
  }

  return (
    <tr className="border-b align-top">
      <td className="py-2 pr-4 break-all">{document.original_filename}</td>
      <td className="py-2 pr-4">
        {label(DOCUMENT_TYPE_LABELS, document.doc_type)}
        {/* The file was read (OCR) and looks like another type. */}
        {document.type_warning && (
          <span className="block text-xs text-amber-700">
            Looks like: {label(DOCUMENT_TYPE_LABELS, document.type_warning)}
          </span>
        )}
      </td>
      <td className="py-2 pr-4">
        {[document.fy, document.period_label].filter(Boolean).join(" · ") || "—"}
      </td>
      <td className="py-2 pr-4 whitespace-nowrap">{formatSize(document.size_bytes)}</td>
      <td className="py-2 pr-4">{formatDateTime(document.created_at)}</td>
      <td className="py-2 pr-4">
        <ul className="space-y-1">
          {document.acknowledgement_of.map((filing) => (
            <li key={filing.compliance_item_id}>
              Acknowledgement of{" "}
              <Link to={"/business/compliance/" + filing.compliance_item_id} className="underline">
                {filingName(filing)}
              </Link>
            </li>
          ))}
          {document.links.map((link) => (
            <li key={link.id}>
              <Link to={"/business/compliance/" + link.compliance_item_id} className="underline">
                {filingName(link)}
              </Link>
            </li>
          ))}
        </ul>
        {document.links.length + document.acknowledgement_of.length === 0 && "—"}
      </td>
      <td className="py-2">
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => run(() => downloadDocument(document))}
          >
            Open
          </Button>
          <Button variant="outline" size="sm" disabled={busy} onClick={onDelete}>
            Delete
          </Button>
        </div>
        {error && (
          <p role="alert" className="mt-1 max-w-60 text-xs text-destructive">
            {error}
          </p>
        )}
      </td>
    </tr>
  );
}
