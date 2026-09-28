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

/** What one price of a catalog service pays for (service_catalog.unit). */
export const SERVICE_UNIT_LABELS = {
  per_return: "per return",
  per_month: "per month",
  per_year: "per year",
  one_time: "one time",
  per_notice: "per notice",
};

/** Kinds of business (businesses.entity_type). */
export const ENTITY_TYPE_LABELS = {
  individual: "Individual (freelancer / gig worker)",
  proprietorship: "Proprietorship",
  partnership: "Partnership firm",
  llp: "LLP",
  private_limited: "Private limited company",
};

/** Regulatory profile lines (regulatory_profiles.msme_tier / gst_scheme / itr_form). */
export const MSME_TIER_LABELS = {
  micro: "Micro",
  small: "Small",
  medium: "Medium",
  not_msme: "Not an MSME",
};

export const GST_SCHEME_LABELS = {
  not_registered: "Not registered",
  regular_monthly: "Regular (monthly)",
  regular_qrmp: "Regular (quarterly, QRMP)",
  composition: "Composition",
};

export const ITR_FORM_LABELS = {
  itr_3: "ITR-3",
  itr_4: "ITR-4",
  itr_5: "ITR-5",
  itr_6: "ITR-6",
};

/** The seven forms we track (compliance_items.form_code). */
export const FORM_LABELS = {
  itr: "Income tax return (ITR)",
  gstr_1: "GSTR-1",
  gstr_3b: "GSTR-3B",
  cmp_08: "CMP-08",
  gstr_4: "GSTR-4",
  tds_24q: "TDS return 24Q (salaries)",
  tds_26q: "TDS return 26Q (other payments)",
};

/** Where a filing is in its lifecycle (compliance_items.status). */
export const COMPLIANCE_STATUS_LABELS = {
  upcoming: "Upcoming",
  docs_pending: "Docs pending",
  ready: "Ready",
  with_ca: "With CA",
  filed: "Filed",
  filed_verified: "Filed–verified",
  overdue: "Overdue",
};

/** Where an engagement between a business and a CA stands (engagements.status). */
export const ENGAGEMENT_STATUS_LABELS = {
  requested: "Requested",
  quoted: "Quote sent",
  active: "Active",
  completed: "Completed",
  declined: "Declined",
  expired: "Expired",
  cancelled: "Cancelled",
};

/** What a tray notification is about (notifications.type). */
export const NOTIFICATION_TYPE_LABELS = {
  deadline_reminder: "Deadline reminder",
  overdue: "Overdue filing",
  engagement_update: "CA request update",
  document_request: "Document request",
  regulatory_update: "Regulatory update",
  account: "Account",
};

/** The label for `code`, or the code itself if the map has no entry (never crash on a new value). */
export function label(labels, code) {
  return labels[code] ?? code;
}
