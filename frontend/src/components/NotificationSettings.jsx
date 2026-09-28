import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { SETTINGS_KEY, saveNotificationSettings, useNotificationSettings } from "@/api/alerts";
import { errorMessage } from "@/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NOTIFICATION_TYPE_LABELS, label } from "@/lib/labels";

// One line under each switch: what the emails are.
const HELP = {
  deadline_reminder: "7, 3 and 1 day before a filing is due.",
  overdue: "Once, when a filing's due date has passed and it is not marked filed.",
  document_request: "When a CA asks for a document, or a requested document arrives.",
  regulatory_update: "When a rule or due date that affects you changes.",
};

/**
 * Email on/off per notification type (business and CA settings pages). Every
 * notification still appears in the tray (the bell); this only decides the emails.
 * Engagement and account emails are always sent, so they get no switch.
 */
export function NotificationSettings() {
  const settings = useNotificationSettings();
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [savingType, setSavingType] = useState(null);

  async function toggle(item) {
    setError(null);
    setSavingType(item.type);
    try {
      const saved = await saveNotificationSettings([
        { type: item.type, email_enabled: !item.email_enabled },
      ]);
      queryClient.setQueryData(SETTINGS_KEY, saved);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setSavingType(null);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">Notification settings</h1>
      <Card>
        <CardHeader>
          <CardTitle>Emails</CardTitle>
          <CardDescription>
            Every notification appears under the bell. Choose which ones are also emailed to you.
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
            <>
              {settings.data.items.map((item) => (
                <label key={item.type} className="flex items-start gap-3 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={item.email_enabled}
                    disabled={savingType !== null}
                    onChange={() => toggle(item)}
                  />
                  <span>
                    {label(NOTIFICATION_TYPE_LABELS, item.type)}
                    <span className="block text-xs text-muted-foreground">{HELP[item.type]}</span>
                  </span>
                </label>
              ))}
              <ul className="space-y-1 border-t pt-4 text-sm text-muted-foreground">
                {settings.data.always_emailed.map((type) => (
                  <li key={type}>{label(NOTIFICATION_TYPE_LABELS, type)}: always emailed</li>
                ))}
              </ul>
            </>
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
