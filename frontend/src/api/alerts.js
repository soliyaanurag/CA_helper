/**
 * All calls to the alerts backend (backend/app/routes/alerts.py): the notification
 * tray, email settings and the penalty estimator.
 * Pages use these functions instead of calling the backend themselves.
 */
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";

// Everything of the tray in the query cache; refreshed after marking entries read.
export const NOTIFICATIONS_KEY = ["alerts", "notifications"];

// How often the bell asks for new notifications while a page is open.
const UNREAD_REFRESH_MS = 60_000;

// { unread } for the bell.
export function useUnreadCount() {
  return useQuery({
    queryKey: [...NOTIFICATIONS_KEY, "unread-count"],
    queryFn: () => apiFetch("/api/v1/alerts/notifications/unread-count"),
    refetchInterval: UNREAD_REFRESH_MS,
  });
}

// The latest tray entries { items, page, page_size, total }, loaded when the tray opens.
export function useNotifications(enabled, pageSize = 10) {
  return useQuery({
    queryKey: [...NOTIFICATIONS_KEY, "list", pageSize],
    queryFn: () => apiFetch(`/api/v1/alerts/notifications?page_size=${pageSize}`),
    enabled,
  });
}

export function markNotificationRead(notificationId) {
  return apiFetch(`/api/v1/alerts/notifications/${notificationId}/read`, { method: "POST" });
}

export function markAllNotificationsRead() {
  return apiFetch("/api/v1/alerts/notifications/read-all", { method: "POST" });
}

// --- Email settings (AL3) ---------------------------------------------------------------

export const SETTINGS_KEY = ["alerts", "settings"];

// { items: [{ type, email_enabled }], always_emailed: [types] }
export function useNotificationSettings() {
  return useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: () => apiFetch("/api/v1/alerts/settings"),
  });
}

// items: [{ type, email_enabled }]. Returns the saved settings.
export function saveNotificationSettings(items) {
  return apiFetch("/api/v1/alerts/settings", { method: "PUT", body: { items } });
}

// --- Penalty estimates (AL5) --------------------------------------------------------------

// One filing's estimate. taxDue ("" or an amount) adds the interest.
export function usePenaltyEstimate(itemId, taxDue, enabled) {
  const query = taxDue ? `?tax_due=${encodeURIComponent(taxDue)}` : "";
  return useQuery({
    queryKey: ["alerts", "penalty", itemId, taxDue],
    queryFn: () => apiFetch(`/api/v1/alerts/penalties/${itemId}${query}`),
    enabled,
  });
}

// The late fees of all overdue filings, for the dashboard (only once registered).
export function usePenaltyExposure(enabled) {
  return useQuery({
    queryKey: ["alerts", "penalties"],
    queryFn: () => apiFetch("/api/v1/alerts/penalties"),
    enabled,
  });
}
