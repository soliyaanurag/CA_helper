import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import {
  NOTIFICATIONS_KEY,
  markAllNotificationsRead,
  markNotificationRead,
  useNotifications,
  useUnreadCount,
} from "@/api/alerts";
import { errorMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/dates";
import { cn } from "@/lib/utils";

/**
 * The bell in the sidebar (every role): the number of unread notifications, and a
 * tray with the latest 10 when clicked. Clicking an entry marks it read and opens its
 * page; "Mark all read" clears the count.
 */
export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const unread = useUnreadCount();
  const count = unread.data?.unread ?? 0;

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="sm"
        aria-label={count > 0 ? `Notifications, ${count} unread` : "Notifications"}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="relative"
      >
        <BellIcon />
        {count > 0 && (
          <span className="absolute -top-1 -right-1 min-w-5 rounded-full bg-red-600 px-1 text-center text-xs text-white tabular-nums">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </Button>
      {open && <Tray onClose={() => setOpen(false)} hasUnread={count > 0} />}
    </div>
  );
}

function Tray({ onClose, hasUnread }) {
  const notifications = useNotifications(true);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState(null);

  function refresh() {
    queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
  }

  async function openEntry(entry) {
    setError(null);
    try {
      if (entry.read_at === null) await markNotificationRead(entry.id);
      refresh();
      onClose();
      if (entry.link) navigate(entry.link);
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }

  async function markAll() {
    setError(null);
    try {
      await markAllNotificationsRead();
      refresh();
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }

  return (
    <div
      role="dialog"
      aria-label="Notifications"
      className="absolute top-full left-0 z-50 mt-2 w-80 rounded-md border bg-background shadow-lg"
    >
      <div className="flex items-center justify-between border-b px-3 py-2">
        <p className="text-sm font-medium">Notifications</p>
        {hasUnread && (
          <Button variant="link" size="sm" className="h-auto p-0" onClick={markAll}>
            Mark all read
          </Button>
        )}
      </div>
      {notifications.isPending && <p className="p-3 text-sm text-muted-foreground">Loading...</p>}
      {notifications.isError && (
        <p role="alert" className="p-3 text-sm text-destructive">
          {errorMessage(notifications.error)}
        </p>
      )}
      {error && (
        <p role="alert" className="px-3 pt-2 text-sm text-destructive">
          {error}
        </p>
      )}
      {notifications.isSuccess && notifications.data.items.length === 0 && (
        <p className="p-3 text-sm text-muted-foreground">No notifications yet.</p>
      )}
      {notifications.isSuccess && notifications.data.items.length > 0 && (
        <ul className="max-h-96 divide-y overflow-y-auto">
          {notifications.data.items.map((entry) => (
            <li key={entry.id}>
              <button
                type="button"
                onClick={() => openEntry(entry)}
                className={cn(
                  "block w-full px-3 py-2 text-left text-sm hover:bg-muted",
                  entry.read_at === null && "bg-sky-50",
                )}
              >
                <span className={cn("block", entry.read_at === null && "font-medium")}>
                  {entry.title}
                </span>
                <span className="block text-xs text-muted-foreground">{entry.body}</span>
                <span className="block text-xs text-muted-foreground">
                  {formatDateTime(entry.created_at)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function BellIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="size-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  );
}
