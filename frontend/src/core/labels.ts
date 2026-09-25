/**
 * Display text for enum codes sent by the API.
 *
 * The API and database store lowercase snake_case codes (e.g. "docs_pending");
 * people see these labels ("Docs pending"). This file is the only place the
 * frontend turns codes into text. Codes and labels must match the "Status values"
 * tables in docs/DATA_MODEL.md; add a map here when a new enum reaches the UI.
 *
 * Usage: label(COMPLIANCE_STATUS_LABELS, item.status)
 */

export const COMPLIANCE_STATUS_LABELS = {
  upcoming: "Upcoming",
  docs_pending: "Docs pending",
  ready: "Ready",
  with_ca: "With CA",
  filed: "Filed",
  filed_verified: "Filed–verified",
  overdue: "Overdue",
} as const satisfies Record<string, string>;

export const ENGAGEMENT_STATUS_LABELS = {
  requested: "Requested",
  accepted: "Accepted",
  quoted: "Quoted",
  active: "Active",
  completed: "Completed",
  declined: "Declined",
  expired: "Expired",
} as const satisfies Record<string, string>;

/** The label for `code`, or the code itself if the map has no entry (never crash on a new value). */
export function label(labels: Readonly<Record<string, string>>, code: string): string {
  return labels[code] ?? code;
}
