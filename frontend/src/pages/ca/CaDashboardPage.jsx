import { Link } from "react-router";

import { errorMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { useCaDashboard } from "@/api/caWorkspace";
import { useCaProfile, useCaServices } from "@/api/marketplace";
import { CA_VERIFICATION_STATUS_LABELS, label } from "@/lib/labels";

/** CA home dashboard. For now a welcome message; clients and urgency scores come later. */
export function CaDashboardPage() {
  const dashboard = useCaDashboard();

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
      <ProfileReminder />
    </div>
  );
}

/** What the CA still has to do before businesses can find them (nothing once verified). */
const REMINDERS = {
  missing: {
    title: "Complete your profile",
    text: "Add your membership and Certificate of Practice numbers, city, languages and specializations. Businesses can find you once an admin has verified them.",
    action: "Complete profile",
  },
  pending: {
    title: "Your profile is waiting for verification",
    text: "An admin is checking your membership and CoP numbers. You will appear in the marketplace once verified.",
    action: "View profile",
  },
  rejected: {
    title: "Your profile needs changes",
    text: "An admin could not confirm your numbers. Correct your details and save to ask for a new check.",
    action: "Edit profile",
  },
};

function ProfileReminder() {
  const profile = useCaProfile();
  const menu = useCaServices();
  if (!profile.isSuccess) return null;
  const reminder = REMINDERS[profile.data?.verification_status ?? "missing"];
  if (!reminder) return null; // verified

  return (
    <Card>
      <CardHeader>
        <CardTitle>{reminder.title}</CardTitle>
        <CardDescription>{reminder.text}</CardDescription>
        <SetupChecklist
          profile={profile.data}
          hasPrices={menu.isSuccess && menu.data.items.length > 0}
        />
        <div>
          <Button asChild>
            <Link to="/ca/profile">{reminder.action}</Link>
          </Button>
        </div>
      </CardHeader>
    </Card>
  );
}

/** The steps to being listed: profile, certificate, prices, then the admin's check. */
function SetupChecklist({ profile, hasPrices }) {
  const steps = [
    ["Profile", Boolean(profile)],
    ["Certificate uploaded", Boolean(profile?.has_certificate)],
    ["Prices set", hasPrices],
  ];
  const status = profile?.verification_status;
  return (
    <ul aria-label="Setup checklist" className="space-y-1 pt-2 text-sm">
      {steps.map(([name, done]) => (
        <li key={name}>
          <span aria-hidden="true">{done ? "✓" : "✗"}</span> {name}
          <span className="sr-only">{done ? ": done" : ": to do"}</span>
        </li>
      ))}
      <li>
        Verification: {status ? label(CA_VERIFICATION_STATUS_LABELS, status) : "not started"}
        {status === "rejected" && profile.rejection_reason && ` (${profile.rejection_reason})`}
      </li>
    </ul>
  );
}
