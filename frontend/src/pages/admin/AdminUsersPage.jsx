import { useState } from "react";
import { Link } from "react-router";

import { useAdminCas, useAdminUsers } from "@/api/admin";
import { errorMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDateTime } from "@/lib/dates";
import { label, USER_ROLE_LABELS } from "@/lib/labels";

const TABS = ["Pending verification", "All users"];

/**
 * /admin/users ("Users & CAs"): the CAs waiting for verification first (each opens the
 * review page), then every account with a role filter and a search.
 */
export function AdminUsersPage() {
  const [tab, setTab] = useState(TABS[0]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Users & CAs</h1>
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
      {tab === TABS[0] ? <PendingCas /> : <AllUsers />}
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
                  <tr key={user.id} className="border-b">
                    <td className="py-2 pr-4">{user.full_name}</td>
                    <td className="py-2 pr-4">{user.email}</td>
                    <td className="py-2 pr-4">{label(USER_ROLE_LABELS, user.role)}</td>
                    <td className="py-2 pr-4">{user.email_verified ? "Yes" : "No"}</td>
                    <td className="py-2">{formatDateTime(user.created_at)}</td>
                  </tr>
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
