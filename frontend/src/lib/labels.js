/**
 * Display text for enum codes sent by the API.
 *
 * The API and database store lowercase snake_case codes (e.g. "ca"); people see
 * these labels ("Chartered Accountant"). This file is the only place the frontend
 * turns codes into text. Codes and labels must match the "Status values" tables in
 * docs/DATA_MODEL.md; add a map here when a new enum reaches the UI.
 *
 * Usage: label(USER_ROLE_LABELS, user.role)
 */

export const USER_ROLE_LABELS = {
  business: "Business",
  ca: "Chartered Accountant",
  admin: "Admin",
};

/** A CA profile's admin check (ca_profiles.verification_status). */
export const CA_VERIFICATION_STATUS_LABELS = {
  pending: "Pending verification",
  verified: "Verified",
  rejected: "Rejected",
};

/**
 * The work a CA can be tagged with (ca_profiles.specializations): the forms we
 * track, then broader areas. Order here is the order on screen.
 */
export const CA_SPECIALIZATION_LABELS = {
  itr: "Income tax return (ITR)",
  gstr_1: "GSTR-1",
  gstr_3b: "GSTR-3B",
  cmp_08: "CMP-08",
  gstr_4: "GSTR-4",
  tds_24q: "TDS return 24Q (salaries)",
  tds_26q: "TDS return 26Q (other payments)",
  gst_registration: "GST registration",
  tax_audit: "Tax audit",
  accounting_bookkeeping: "Accounting & bookkeeping",
  income_tax_notices: "Income-tax notices",
  company_llp_compliance: "Company / LLP compliance",
  startup_msme_advisory: "Startup & MSME advisory",
};

/** Languages a CA works in (ca_profiles.languages). */
export const CA_LANGUAGE_LABELS = {
  english: "English",
  hindi: "Hindi",
  bengali: "Bengali",
  gujarati: "Gujarati",
  kannada: "Kannada",
  malayalam: "Malayalam",
  marathi: "Marathi",
  odia: "Odia",
  punjabi: "Punjabi",
  tamil: "Tamil",
  telugu: "Telugu",
  urdu: "Urdu",
};

/** The label for `code`, or the code itself if the map has no entry (never crash on a new value). */
export function label(labels, code) {
  return labels[code] ?? code;
}
