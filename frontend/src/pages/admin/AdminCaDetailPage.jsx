import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";

import {
  ADMIN_CAS_KEY,
  ADMIN_STATS_KEY,
  rejectCa,
  useAdminCa,
  useCertificateFile,
  verifyCa,
} from "@/api/admin";
import { errorMessage } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { formatDateTime } from "@/lib/dates";
import {
  CA_LANGUAGE_LABELS,
  CA_SPECIALIZATION_LABELS,
  CA_VERIFICATION_STATUS_LABELS,
  label,
} from "@/lib/labels";

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
