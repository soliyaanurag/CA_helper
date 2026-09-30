import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";

import {
  addNewsSource,
  ADMIN_CAS_KEY,
  ADMIN_STATS_KEY,
  errorMessage,
  NEWS_SOURCES_KEY,
  REGULATORY_CHANGES_KEY,
  rejectCa,
  scanNewsNow,
  setNewsSourceEnabled,
  useAdminCa,
  useAdminCas,
  useAdminDashboard,
  useAdminStats,
  useAdminUsers,
  useCertificateFile,
  useNewsSources,
  useRegulatoryChanges,
  verifyCa,
} from "@/api";
import { RegulatoryChangeCard } from "@/components/shared";
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
  formatDateTime,
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

// Filings across all businesses by status, and how many due ones were late.
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
                  <th className="py-2 font-medium">Joined</th>
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

function UserRow({ user }) {
  return (
    <tr className="border-b align-top">
      <td className="py-2 pr-4">{user.full_name}</td>
      <td className="py-2 pr-4">{user.email}</td>
      <td className="py-2 pr-4">{label(USER_ROLE_LABELS, user.role)}</td>
      <td className="py-2 pr-4">{user.email_verified ? "Yes" : "No"}</td>
      <td className="py-2">{formatDateTime(user.created_at)}</td>
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
 * reason. The CA is emailed either way.
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

const REGULATORY_TABS = ["Changes", "Sources"];

/**
 * /admin/regulatory ("Regulatory news"): the changes found in the news. A change Gemini
 * extracted was sent at once to the businesses it affects and their CAs; one found by
 * keywords only was sent to nobody. The Sources tab lists the news sites and runs a scan.
 */
export function RegulatoryAdminPage() {
  const [tab, setTab] = useState(REGULATORY_TABS[0]);

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Regulatory news</h1>
        <p className="text-sm text-muted-foreground">
          Changes found in the news every morning. Those Gemini read are sent to the affected
          users at once; those found by keywords only are not sent.
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
      {tab === REGULATORY_TABS[0] ? <Changes /> : <Sources />}
    </div>
  );
}

function Changes() {
  const changes = useRegulatoryChanges();

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
    return <p className="text-sm text-muted-foreground">No changes found yet.</p>;
  }
  return (
    <div className="space-y-4">
      {changes.data.map((change) => (
        <RegulatoryChangeCard key={change.id} change={change}>
          <p className="text-muted-foreground">
            {change.notified_at
              ? `Sent ${formatDateTime(change.notified_at)} · ${change.match_count} business(es) told`
              : "Not sent to anyone"}
          </p>
        </RegulatoryChangeCard>
      ))}
    </div>
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
                {scanResult.new_articles} new article(s), {scanResult.changes} change(s) found
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
