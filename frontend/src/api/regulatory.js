/**
 * All calls to the regulatory monitor (backend/app/routes/regulatory.py). Admins only.
 */
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";

// Names in the query cache; the page refreshes them after an action.
export const REGULATORY_CHANGES_KEY = ["regulatory", "changes"];
export const NEWS_SOURCES_KEY = ["regulatory", "sources"];

// Changes found in the news, newest first. `status` is "pending", "approved" or "rejected".
// Each: { id, change_type, summary, form_codes, affected_categories, dates, status,
// article_title, article_url, source_name, published_at, match_count, ... }
export function useRegulatoryChanges(status) {
  return useQuery({
    queryKey: [...REGULATORY_CHANGES_KEY, status],
    queryFn: () => apiFetch("/api/v1/admin/regulatory/changes?status=" + status),
  });
}

// Approve a change: the affected businesses and their CAs are told.
export function approveChange(changeId) {
  return apiFetch(`/api/v1/admin/regulatory/changes/${changeId}/approve`, { method: "POST" });
}

// Reject a change: nobody is told.
export function rejectChange(changeId) {
  return apiFetch(`/api/v1/admin/regulatory/changes/${changeId}/reject`, { method: "POST" });
}

// The news sources: [{ id, name, url, kind: "rss" | "html", enabled }].
export function useNewsSources() {
  return useQuery({
    queryKey: NEWS_SOURCES_KEY,
    queryFn: () => apiFetch("/api/v1/admin/regulatory/sources"),
  });
}

export function addNewsSource(source) {
  return apiFetch("/api/v1/admin/regulatory/sources", { method: "POST", body: source });
}

export function setNewsSourceEnabled(sourceId, enabled) {
  return apiFetch(`/api/v1/admin/regulatory/sources/${sourceId}`, {
    method: "PUT",
    body: { enabled },
  });
}

// Run the news scan now. Returns { sources, blocked_by_robots, failed, new_articles, changes }.
export function scanNewsNow() {
  return apiFetch("/api/v1/admin/regulatory/scan", { method: "POST" });
}
