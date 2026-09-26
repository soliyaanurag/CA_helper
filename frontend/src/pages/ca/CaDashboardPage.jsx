import { Link } from "react-router";

import { errorMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { useCaDashboard } from "@/api/caWorkspace";
import { useCaProfile } from "@/api/marketplace";

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
  if (!profile.isSuccess) return null;
  const reminder = REMINDERS[profile.data?.verification_status ?? "missing"];
  if (!reminder) return null; // verified

  return (
    <Card>
      <CardHeader>
        <CardTitle>{reminder.title}</CardTitle>
        <CardDescription>{reminder.text}</CardDescription>
        <div>
          <Button asChild>
            <Link to="/ca/profile">{reminder.action}</Link>
          </Button>
        </div>
      </CardHeader>
    </Card>
  );
}
