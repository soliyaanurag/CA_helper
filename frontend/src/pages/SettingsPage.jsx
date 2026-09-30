import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage, saveSettings, SETTINGS_KEY, useSettings } from "@/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui";

/**
 * /business/settings and /ca/settings: one switch for the notification emails.
 * Every notification still appears under the bell; login and password codes are
 * always emailed.
 */
export function SettingsPage() {
  const settings = useSettings();
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  async function toggle() {
    setError(null);
    setSaving(true);
    try {
      const saved = await saveSettings(!settings.data.email_notifications);
      queryClient.setQueryData(SETTINGS_KEY, saved);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">Notification settings</h1>
      <Card>
        <CardHeader>
          <CardTitle>Emails</CardTitle>
          <CardDescription>
            Every notification appears under the bell. Choose whether they are also emailed to you.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {settings.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
          {settings.isError && (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage(settings.error)}
            </p>
          )}
          {settings.isSuccess && (
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={settings.data.email_notifications}
                disabled={saving}
                onChange={toggle}
              />
              <span>
                Email me my notifications
                <span className="block text-xs text-muted-foreground">
                  Deadline reminders, overdue filings, document requests, CA request updates and
                  rule changes. Login and password codes are always emailed.
                </span>
              </span>
            </label>
          )}
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
