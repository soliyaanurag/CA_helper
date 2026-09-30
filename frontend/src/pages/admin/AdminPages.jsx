import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";

import {
  addNewsSource,
  ADMIN_CAS_KEY,
  ADMIN_STATS_KEY,
  approveChange,
  errorMessage,
  NEWS_SOURCES_KEY,
  reactivateUser,
  REGULATORY_CHANGES_KEY,
  rejectCa,
  rejectChange,
  scanNewsNow,
  setNewsSourceEnabled,
  suspendUser,
  useAdminCa,
  useAdminCas,
  useAdminDashboard,
  useAdminStats,
  useAdminUsers,
  useAuditLog,
  useCertificateFile,
  useNewsSources,
  useRegulatoryChanges,
  verifyCa,
} from "@/api";
import { useAuth } from "@/auth";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
} from "@/components/ui";
import {
  CA_LANGUAGE_LABELS,
  CA_SPECIALIZATION_LABELS,
  CA_VERIFICATION_STATUS_LABELS,
  COMPLIANCE_STATUS_LABELS,
  ENTITY_TYPE_LABELS,
  FORM_LABELS,
  formatDate,
  formatDateTime,
  GST_SCHEME_LABELS,
  label,
  USER_ROLE_LABELS,
} from "@/lib";

// --- AdminDashboardPage ------------------------------------------------------------------------

/** Admin home page: a welcome message and the counts that need an eye on them. */
export function AdminDashboardPage() {
  const dashboard = useAdminDashboard();
  const stats = useAdminStats();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">
        {dashboard.isPending
          ? "Loading..."
          : dashboard.isError
            ? "Dashboard"
            : dashboard.data.message}
      </h1>
      {dashboard.isError && (
        <Card>
          <CardHeader>
            <CardTitle>Could not load the dashboard</CardTitle>
            <CardDescription>{errorMessage(dashboard.error)}</CardDescription>
          </CardHeader>
        </Card>
      )}
      {stats.isSuccess && <Counts stats={stats.data} />}
      {stats.isSuccess && <Filings stats={stats.data} />}
    </div>
  );
}

function Counts({ stats }) {
  const cards = [
    ["Business users", stats.users_by_role.business],
    ["CAs", stats.users_by_role.ca],
    ["Admins", stats.users_by_role.admin],
    ["Businesses registered", stats.businesses],
    ["CAs pending verification", stats.cas_by_status.pending, "/admin/users"],
    ["Open engagements", stats.open_engagements],
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map(([title, value, link]) => (
        <Card key={title}>
          <CardHeader>
            <CardDescription>{title}</CardDescription>
            <CardTitle className="text-2xl tabular-nums">{value}</CardTitle>
            {link && value > 0 && (
              <Link to={link} className="text-sm text-primary underline-offset-4 hover:underline">
                Review them
              </Link>
            )}
          </CardHeader>
        </Card>
      ))}
    </div>
  );
}

// Filings across all businesses by status, and how many due ones were late (AD5).
function Filings({ stats }) {
  const rate = stats.overdue_rate === null ? "No filing is due yet" : `${stats.overdue_rate}%`;
  return (
    <Card>
      <CardHeader>
        <CardDescription>Overdue rate</CardDescription>
        <CardTitle className="text-2xl tabular-nums">{rate}</CardTitle>
        <CardDescription>
          {stats.filings_late} of {stats.filings_due_so_far} filings due so far were not filed on
          time (still unfiled, or filed after the due date).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="mb-2 text-sm font-medium">Filings by status</p>
        <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(stats.filings_by_status).map(([status, count]) => (
            <div key={status} className="flex justify-between gap-2">
              <dt>{label(COMPLIANCE_STATUS_LABELS, status)}</dt>
              <dd className="tabular-nums">{count}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

// --- AdminUsersPage ----------------------------------------------------------------------------

const USER_TABS = ["Pending verification", "All users"];

/**
 * /admin/users ("Users & CAs"): the CAs waiting for verification first (each opens the
 * review page), then every account with a role filter and a search.
 */
export function AdminUsersPage() {
  const [tab, setTab] = useState(USER_TABS[0]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Users & CAs</h1>
      <div role="tablist" className="flex gap-2">
        {USER_TABS.map((name) => (
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
      {tab === USER_TABS[0] ? <PendingCas /> : <AllUsers />}
    </div>
  );
}

function PendingCas() {
  const cas = useAdminCas("pending");
  if (cas.isPending) return <p className="text-sm text-muted-foreground">Loading...</p>;
  if (cas.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {errorMessage(cas.error)}
      </p>
    );
  }
  if (cas.data.length === 0) {
    return <p className="text-sm text-muted-foreground">No CA is waiting for verification.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b text-muted-foreground">
          <tr>
            <th className="py-2 pr-4 font-medium">CA</th>
            <th className="py-2 pr-4 font-medium">Membership no.</th>
            <th className="py-2 pr-4 font-medium">City</th>
            <th className="py-2 pr-4 font-medium">Certificate</th>
            <th className="py-2 pr-4 font-medium">Waiting since</th>
            <th className="py-2 font-medium" />
          </tr>
        </thead>
        <tbody>
          {cas.data.map((ca) => (
            <tr key={ca.id} className="border-b">
              <td className="py-2 pr-4">
                {ca.full_name}
                <div className="text-xs text-muted-foreground">{ca.email}</div>
              </td>
              <td className="py-2 pr-4">{ca.membership_no}</td>
              <td className="py-2 pr-4">{ca.city}</td>
              <td className="py-2 pr-4">{ca.has_certificate ? "Uploaded" : "Missing"}</td>
              <td className="py-2 pr-4">{formatDateTime(ca.updated_at)}</td>
              <td className="py-2">
                <Link
                  to={"/admin/cas/" + ca.id}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  Review {ca.full_name}
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const SELECT_CLASS =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

function AllUsers() {
  const [filters, setFilters] = useState({ role: "", search: "", page: 1 });
  const users = useAdminUsers(filters);

  function onSearch(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setFilters({ role: form.get("role"), search: form.get("search").trim(), page: 1 });
  }

  return (
    <div className="space-y-4">
      <form className="flex flex-wrap items-end gap-3" onSubmit={onSearch}>
        <div className="space-y-2">
          <Label htmlFor="role">Role</Label>
          <select id="role" name="role" defaultValue={filters.role} className={SELECT_CLASS}>
            <option value="">All</option>
            {Object.entries(USER_ROLE_LABELS).map(([code, text]) => (
              <option key={code} value={code}>
                {text}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="search">Name or email</Label>
          <Input id="search" name="search" defaultValue={filters.search} />
        </div>
        <Button type="submit">Search</Button>
      </form>

      {users.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {users.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(users.error)}
        </p>
      )}
      {users.isSuccess && (
        <>
          <p className="text-sm text-muted-foreground">
            {users.data.total === 1 ? "1 account" : `${users.data.total} accounts`}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b text-muted-foreground">
                <tr>
                  <th className="py-2 pr-4 font-medium">Name</th>
                  <th className="py-2 pr-4 font-medium">Email</th>
                  <th className="py-2 pr-4 font-medium">Role</th>
                  <th className="py-2 pr-4 font-medium">Email verified</th>
                  <th className="py-2 pr-4 font-medium">Joined</th>
                  <th className="py-2 pr-4 font-medium">Account</th>
                  <th className="py-2 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.data.items.map((user) => (
                  <UserRow key={user.id} user={user} />
                ))}
              </tbody>
            </table>
          </div>
          <Pager data={users.data} onPage={(page) => setFilters({ ...filters, page })} />
        </>
      )}
    </div>
  );
}

// One account, with Suspend / Reactivate (AD4). Admins cannot suspend themselves.
function UserRow({ user }) {
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run(action) {
    setError(null);
    setBusy(true);
    try {
      await action();
      queryClient.invalidateQueries({ queryKey: ["admin"] });
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  function onSuspend() {
    const reason = window.prompt(
      `Suspend ${user.full_name}? They cannot log in until reactivated.` +
        (user.role === "ca" ? " Their open requests are cancelled." : "") +
        "\n\nReason (optional, kept in the audit log):",
    );
    if (reason === null) return; // cancelled
    run(() => suspendUser(user.id, reason.trim()));
  }

  return (
    <tr className="border-b align-top">
      <td className="py-2 pr-4">{user.full_name}</td>
      <td className="py-2 pr-4">{user.email}</td>
      <td className="py-2 pr-4">{label(USER_ROLE_LABELS, user.role)}</td>
      <td className="py-2 pr-4">{user.email_verified ? "Yes" : "No"}</td>
      <td className="py-2 pr-4">{formatDateTime(user.created_at)}</td>
      <td className="py-2 pr-4">{user.is_active ? "Active" : "Suspended"}</td>
      <td className="py-2">
        {user.id !== me?.id &&
          (user.is_active ? (
            <Button variant="outline" size="sm" disabled={busy} onClick={onSuspend}>
              Suspend
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => run(() => reactivateUser(user.id))}
            >
              Reactivate
            </Button>
          ))}
        {error && (
          <p role="alert" className="mt-1 text-xs text-destructive">
            {error}
          </p>
        )}
      </td>
    </tr>
  );
}

function Pager({ data, onPage }) {
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  if (pages === 1) return null;
  return (
    <div className="flex items-center gap-3 text-sm">
      <Button variant="outline" disabled={data.page <= 1} onClick={() => onPage(data.page - 1)}>
        Previous
      </Button>
      <span>
        Page {data.page} of {pages}
      </span>
      <Button variant="outline" disabled={data.page >= pages} onClick={() => onPage(data.page + 1)}>
        Next
      </Button>
    </div>
  );
}

// --- AdminCaDetailPage -------------------------------------------------------------------------

/**
 * /admin/cas/:caId: an admin checks a CA's numbers against their Certificate of
 * Practice, then verifies them (listed in the marketplace) or rejects them with a
 * reason. The CA is emailed either way; the action is written to the audit log.
 */
export function AdminCaDetailPage() {
  const { caId } = useParams();
  const ca = useAdminCa(caId);

  return (
    <div className="max-w-3xl space-y-6">
      <Link to="/admin/users" className="text-sm text-primary underline-offset-4 hover:underline">
        ← Back to Users & CAs
      </Link>
      {ca.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {ca.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(ca.error)}
        </p>
      )}
      {ca.isSuccess && (
        <>
          <Details ca={ca.data} />
          <Certificate ca={ca.data} />
          <Decision ca={ca.data} />
        </>
      )}
    </div>
  );
}

function Details({ ca }) {
  const rows = [
    ["Email", ca.email],
    ["ICAI membership number", ca.membership_no],
    ["Certificate of Practice number", ca.cop_number],
    ["City", ca.city],
    ["Years of experience", ca.years_experience],
    ["Capacity (clients at a time)", ca.capacity],
    ["Free (pro-bono) slots per month", ca.pro_bono_slots_per_month],
    [
      "Specializations",
      ca.specializations.map((code) => label(CA_SPECIALIZATION_LABELS, code)).join(", "),
    ],
    ["Languages", ca.languages.map((code) => label(CA_LANGUAGE_LABELS, code)).join(", ")],
    ["About", ca.about || "—"],
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold">{ca.full_name}</h1>
          <Badge variant="secondary">
            {label(CA_VERIFICATION_STATUS_LABELS, ca.verification_status)}
          </Badge>
        </CardTitle>
        <CardDescription>Last changed {formatDateTime(ca.updated_at)}</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="divide-y text-sm">
          {rows.map(([name, value]) => (
            <div key={name} className="grid gap-1 py-2 sm:grid-cols-3">
              <dt className="text-muted-foreground">{name}</dt>
              <dd className="sm:col-span-2">{value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

/** Loads the certificate (admins only) and offers it as a link that opens it. */
function Certificate({ ca }) {
  const file = useCertificateFile(ca.id, ca.has_certificate);
  // A local link to the downloaded file; freed again when the page closes.
  const url = useMemo(() => (file.data ? URL.createObjectURL(file.data) : null), [file.data]);
  useEffect(() => () => url && URL.revokeObjectURL(url), [url]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Certificate of Practice</CardTitle>
        <CardDescription>
          {!ca.has_certificate
            ? "Not uploaded yet: the CA cannot be verified until they upload it."
            : "Check that the name and numbers match the profile above."}
        </CardDescription>
      </CardHeader>
      {ca.has_certificate && (
        <CardContent className="text-sm">
          {file.isError && (
            <p role="alert" className="text-destructive">
              {errorMessage(file.error)}
            </p>
          )}
          {url ? (
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="text-primary underline-offset-4 hover:underline"
            >
              Open the certificate
            </a>
          ) : (
            !file.isError && (
              <span className="text-muted-foreground">Loading the certificate...</span>
            )
          )}
        </CardContent>
      )}
    </Card>
  );
}

function Decision({ ca }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);
  const [busy, setBusy] = useState(false);

  async function decide(action, doneText) {
    setError(null);
    setDone(null);
    setBusy(true);
    try {
      const updated = await action();
      queryClient.setQueryData([...ADMIN_CAS_KEY, "one", ca.id], updated);
      queryClient.invalidateQueries({ queryKey: ADMIN_CAS_KEY, exact: false });
      queryClient.invalidateQueries({ queryKey: ADMIN_STATS_KEY });
      setDone(doneText);
      setReason("");
    } catch (decideError) {
      setError(errorMessage(decideError));
    }
    setBusy(false);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Decision</CardTitle>
        <CardDescription>
          Verifying lists the CA in the marketplace. Rejecting needs a reason, which the CA sees.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button
          onClick={() => decide(() => verifyCa(ca.id), "Verified. The CA has been emailed.")}
          disabled={busy || ca.verification_status === "verified" || !ca.has_certificate}
        >
          Verify
        </Button>
        <div className="space-y-2">
          <Label htmlFor="reason">Reason for rejecting</Label>
          <textarea
            id="reason"
            rows={2}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          />
          <Button
            variant="outline"
            onClick={() =>
              decide(() => rejectCa(ca.id, reason), "Rejected. The CA has been emailed.")
            }
            disabled={busy || !reason.trim()}
          >
            Reject
          </Button>
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {done && (
          <p role="status" className="text-sm text-muted-foreground">
            {done}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// --- RegulatoryAdminPage -----------------------------------------------------------------------

const REGULATORY_TABS = ["To review", "Reviewed", "Sources"];

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
  const [tab, setTab] = useState(REGULATORY_TABS[0]);

  let content = <Sources />;
  if (tab === REGULATORY_TABS[0]) {
    content = <Changes status="pending" />;
  } else if (tab === REGULATORY_TABS[1]) {
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
        {REGULATORY_TABS.map((name) => (
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

// --- AdminAuditLogPage -------------------------------------------------------------------------

// What each recorded action means, in words.
const ACTION_LABELS = {
  "ca_profile.verify": "Verified a CA",
  "ca_profile.reject": "Rejected a CA",
  "user.suspend": "Suspended an account",
  "user.reactivate": "Reactivated an account",
};

// The details worth showing, e.g. "Reason: Fake documents · Requests cancelled: 2".
function detailsText(details) {
  if (!details) return "";
  const parts = [];
  if (details.reason) parts.push(`Reason: ${details.reason}`);
  if (details.cancelled_requests) parts.push(`Requests cancelled: ${details.cancelled_requests}`);
  return parts.join(" · ");
}

/** /admin/audit ("Audit log"): every admin action, newest first (AD8). */
export function AdminAuditLogPage() {
  const [page, setPage] = useState(1);
  const log = useAuditLog(page);
  const pages = log.isSuccess ? Math.max(1, Math.ceil(log.data.total / log.data.page_size)) : 1;

  return (
    <div className="max-w-5xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Audit log</h1>
        <p className="text-sm text-muted-foreground">
          Every admin action, newest first. Entries are never changed or deleted.
        </p>
      </div>
      {log.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {log.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(log.error)}
        </p>
      )}
      {log.isSuccess && log.data.items.length === 0 && (
        <p className="text-sm text-muted-foreground">No admin actions yet.</p>
      )}
      {log.isSuccess && log.data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b text-muted-foreground">
              <tr>
                <th className="py-2 pr-4 font-medium">When</th>
                <th className="py-2 pr-4 font-medium">Admin</th>
                <th className="py-2 pr-4 font-medium">Action</th>
                <th className="py-2 pr-4 font-medium">Who / what</th>
                <th className="py-2 font-medium">Details</th>
              </tr>
            </thead>
            <tbody>
              {log.data.items.map((entry) => (
                <tr key={entry.id} className="border-b align-top">
                  <td className="py-2 pr-4 whitespace-nowrap">
                    {formatDateTime(entry.created_at)}
                  </td>
                  <td className="py-2 pr-4">{entry.admin_name ?? "—"}</td>
                  <td className="py-2 pr-4">{ACTION_LABELS[entry.action] ?? entry.action}</td>
                  <td className="py-2 pr-4">{entry.target_name ?? entry.target_type}</td>
                  <td className="py-2">{detailsText(entry.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pages > 1 && (
        <div className="flex items-center gap-3 text-sm">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Previous
          </Button>
          <span>
            Page {page} of {pages}
          </span>
          <Button variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
