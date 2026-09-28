/**
 * API calls for the admin module: TanStack Query hooks around the API client.
 * Every call goes through apiFetch(), so failures are ApiRequestError (code, message).
 */
import { useQuery } from "@tanstack/react-query";

import { apiDownload, apiFetch } from "@/api/client";

/** GET /api/v1/admin/dashboard */
export function useAdminDashboard() {
  return useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: () => apiFetch("/api/v1/admin/dashboard"),
  });
}

// Names in the query cache; the CA review page refreshes them after a decision.
export const ADMIN_CAS_KEY = ["admin", "cas"];
export const ADMIN_STATS_KEY = ["admin", "stats"];

/**
 * GET /api/v1/admin/stats: users by role, businesses, CAs by status, open engagements, and
 * filings_by_status, filings_due_so_far, filings_late, overdue_rate (percent or null).
 */
export function useAdminStats() {
  return useQuery({
    queryKey: ADMIN_STATS_KEY,
    queryFn: () => apiFetch("/api/v1/admin/stats"),
  });
}

/** GET /api/v1/admin/users?role=&search=&page= (empty filters are not sent) */
export function useAdminUsers({ role, search, page }) {
  const params = new URLSearchParams();
  if (role) params.set("role", role);
  if (search) params.set("search", search);
  if (page > 1) params.set("page", page);
  const url = "/api/v1/admin/users" + (params.toString() ? "?" + params : "");
  return useQuery({ queryKey: ["admin", "users", url], queryFn: () => apiFetch(url) });
}

/** GET /api/v1/admin/cas?status=pending: CA profiles, the longest-waiting first */
export function useAdminCas(status) {
  return useQuery({
    queryKey: [...ADMIN_CAS_KEY, status],
    queryFn: () => apiFetch("/api/v1/admin/cas?status=" + status),
  });
}

/** GET /api/v1/admin/cas/<id>: one CA with everything to check */
export function useAdminCa(caId) {
  return useQuery({
    queryKey: [...ADMIN_CAS_KEY, "one", caId],
    queryFn: () => apiFetch("/api/v1/admin/cas/" + caId),
  });
}

/** The CA's Certificate of Practice file (a Blob), when they have uploaded one. */
export function useCertificateFile(caId, enabled) {
  return useQuery({
    queryKey: [...ADMIN_CAS_KEY, "certificate", caId],
    queryFn: () => apiDownload("/api/v1/admin/cas/" + caId + "/certificate"),
    enabled,
  });
}

export function verifyCa(caId) {
  return apiFetch("/api/v1/admin/cas/" + caId + "/verify", { method: "POST" });
}

export function rejectCa(caId, reason) {
  return apiFetch("/api/v1/admin/cas/" + caId + "/reject", { method: "POST", body: { reason } });
}

// Suspend an account (it cannot log in); the reason is optional and kept in the audit log.
export function suspendUser(userId, reason) {
  return apiFetch("/api/v1/admin/users/" + userId + "/suspend", {
    method: "POST",
    body: { reason: reason || null },
  });
}

export function reactivateUser(userId) {
  return apiFetch("/api/v1/admin/users/" + userId + "/reactivate", { method: "POST" });
}

/**
 * GET /api/v1/admin/audit-log?page=: { items: [{ id, admin_name, action, target_type,
 * target_id, target_name, details, created_at }], page, page_size, total }, newest first.
 */
export function useAuditLog(page) {
  return useQuery({
    queryKey: ["admin", "audit-log", page],
    queryFn: () => apiFetch("/api/v1/admin/audit-log?page=" + page),
  });
}
