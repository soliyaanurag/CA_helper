/**
 * Display text for enum codes sent by the API.
 *
 * The API and database store lowercase snake_case codes (e.g. "docs_pending");
 * people see these labels ("Docs pending"). This file is the only place the
 * frontend turns codes into text. Codes and labels must match the "Status values"
 * tables in docs/DATA_MODEL.md; add a map here when a new enum reaches the UI.
 *
 * Usage: label(USER_ROLE_LABELS, user.role)
 */

export const USER_ROLE_LABELS = {
  business: "Business",
  ca: "Chartered Accountant",
  admin: "Admin",
} as const satisfies Record<string, string>;

/** The label for `code`, or the code itself if the map has no entry (never crash on a new value). */
export function label(labels: Readonly<Record<string, string>>, code: string): string {
  return labels[code] ?? code;
}
