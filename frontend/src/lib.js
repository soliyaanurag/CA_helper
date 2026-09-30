import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { z } from "zod";

// --- utils -------------------------------------------------------------------------------------

/**
 * Join class names (clsx) and let later Tailwind classes win over earlier ones
 * (tailwind-merge), e.g. cn("px-2", isActive && "px-4") -> "px-4". The standard shadcn/ui helper.
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// --- labels ------------------------------------------------------------------------------------

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

/**
 * Forms renamed by law, shown under the new name from the first financial year given (the
 * code stays). The Income-tax Act, 2025 renamed the quarterly TDS statements from tax year
 * 2026-27: 24Q is Form 138 and 26Q is Form 140. Same list as RENAMED_FORMS in
 * backend/app/services/compliance_service.py.
 */
export const RENAMED_FORMS = {
  tds_24q: { fromFy: "2026-27", name: "Form 138 (earlier 24Q)" },
  tds_26q: { fromFy: "2026-27", name: "Form 140 (earlier 26Q)" },
};

/**
 * The name of one filing's form: FORM_LABELS, or the new name of a renamed form when the
 * filing's period label ("Q2 2026-27") is in a financial year from the rename on.
 */
export function filingFormLabel(formCode, periodLabel) {
  const renamed = RENAMED_FORMS[formCode];
  const fy = /(\d{4}-\d{2})$/.exec(periodLabel ?? "")?.[1];
  if (renamed && fy && fy >= renamed.fromFy) return renamed.name;
  return label(FORM_LABELS, formCode);
}

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

/** What kind of file a document is (documents.doc_type). */
export const DOCUMENT_TYPE_LABELS = {
  gst_certificate: "GST registration certificate",
  pan_card: "PAN card",
  sales_register: "Sales register",
  purchase_register: "Purchase register",
  bank_statement: "Bank statement",
  invoice: "Invoice",
  salary_register: "Salary register",
  tds_challan: "TDS challan",
  acknowledgement: "Filing acknowledgement",
  certificate_of_practice: "Certificate of Practice (CA)",
  other: "Other",
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

// --- money -------------------------------------------------------------------------------------

/**
 * Showing rupee amounts. The API sends money as strings like "2500.00".
 *
 *   formatRupees("2500.00")  -> "₹2,500"
 *   formatRupees("99.50")    -> "₹99.50"
 */

// Indian digit grouping (₹1,00,000); paise only when there are some.
export function formatRupees(amount) {
  const number = Number(amount);
  if (Number.isInteger(number)) {
    return "₹" + number.toLocaleString("en-IN");
  }
  return (
    "₹" + number.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  );
}

// The typical price range of a catalog service (GET /api/v1/marketplace/services),
// e.g. "₹600 – ₹1,000, median ₹700 (3 CAs)". The API sends no range until
// enough CAs offer the service.
export function typicalRangeText(service) {
  if (service.median_price === null) {
    return "Not enough data yet";
  }
  return (
    formatRupees(service.min_price) +
    " – " +
    formatRupees(service.max_price) +
    ", median " +
    formatRupees(service.median_price) +
    " (" +
    service.ca_count +
    " CAs)"
  );
}

// Where a price sits against the median of all CAs, or null if there is no median yet.
export function comparedToMedian(price, median) {
  if (median === null || median === undefined) {
    return null;
  }
  if (Number(price) < Number(median)) {
    return "Below the median";
  }
  if (Number(price) > Number(median)) {
    return "Above the median";
  }
  return "At the median";
}

// --- dates -------------------------------------------------------------------------------------

/**
 * Showing dates. The API sends dates as "2026-09-20" and times as UTC timestamps
 * ("2026-09-27T10:30:00+00:00"); people in India see them in Indian time.
 *
 *   formatDate("2026-09-20")               -> "20 Sept 2026"
 *   formatDateTime("2026-09-27T10:30:00Z") -> "27 Sept 2026, 4:00 pm"
 */

// A plain date. It is built from its parts, so no time zone can move it to the day before.
export function formatDate(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

// A moment in time, shown in Indian time.
export function formatDateTime(isoTimestamp) {
  return new Date(isoTimestamp).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  });
}

const MILLISECONDS_PER_MINUTE = 60 * 1000;
const MILLISECONDS_PER_DAY = 24 * 60 * MILLISECONDS_PER_MINUTE;

// Today's date as "2026-09-27", in the browser's own time zone (people use the app in India).
export function todayIso() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

// Whole days from today to a date: 0 today, negative once it has passed.
export function daysUntil(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  const [nowYear, nowMonth, nowDay] = todayIso().split("-").map(Number);
  const milliseconds = Date.UTC(year, month - 1, day) - Date.UTC(nowYear, nowMonth - 1, nowDay);
  return Math.round(milliseconds / MILLISECONDS_PER_DAY);
}

// "Today", "In 1 day", "In 12 days", "3 days ago".
export function daysLeftText(isoDate) {
  const days = daysUntil(isoDate);
  if (days === 0) {
    return "Today";
  }
  if (days === 1) {
    return "In 1 day";
  }
  if (days > 1) {
    return "In " + days + " days";
  }
  if (days === -1) {
    return "1 day ago";
  }
  return -days + " days ago";
}

// "2026-10-13" -> "October 2026".
export function monthLabel(isoDate) {
  const [year, month] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("en-IN", {
    month: "long",
    year: "numeric",
  });
}

// How long until a moment, for request deadlines: "expires in 31 h", "expires in 20 min".
export function expiresInText(isoTimestamp) {
  const minutes = Math.floor((new Date(isoTimestamp) - new Date()) / MILLISECONDS_PER_MINUTE);
  if (minutes <= 0) {
    // The worker marks the request "expired" within 15 minutes; until then it is still requested.
    return "answer time over";
  }
  if (minutes < 60) {
    return "expires in " + minutes + " min";
  }
  return "expires in " + Math.floor(minutes / 60) + " h";
}

// True once a moment (e.g. a request's answer deadline) has passed.
export function isPast(isoTimestamp) {
  return new Date(isoTimestamp) <= new Date();
}

// --- gstin -------------------------------------------------------------------------------------

/**
 * GSTIN checks, the same as backend/app/utils/gstin.py (and the same messages).
 *
 *   gstinError("27ABCDE1234F1Z0", "ABCDE1234F", "27")   -> null (fine)
 *
 * A GSTIN is <state code 2><PAN 10><entity 1>Z<check character 1>. The check character
 * comes from the other 14: each character's value (0-9, A-Z = 0-35) is multiplied by
 * 1 and 2 in turn, the base-36 digits of the products are added up, and the check
 * character makes the total a multiple of 36.
 */

const CHARACTERS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";

export function gstinCheckCharacter(first14) {
  let total = 0;
  for (let index = 0; index < first14.length; index++) {
    const product = CHARACTERS.indexOf(first14[index]) * (index % 2 === 0 ? 1 : 2);
    total += Math.floor(product / 36) + (product % 36);
  }
  return CHARACTERS[(36 - (total % 36)) % 36];
}

/** What is wrong with a well-formed GSTIN for this PAN and state (name + code), or null. */
export function gstinError(gstin, pan, stateName, stateCode) {
  if (gstinCheckCharacter(gstin.slice(0, 14)) !== gstin[14]) {
    return "This GSTIN is not valid: its last character does not match. Check for a typo.";
  }
  if (stateCode && gstin.slice(0, 2) !== stateCode) {
    return `This GSTIN starts with ${gstin.slice(0, 2)}, but the code of ${stateName} is ${stateCode}.`;
  }
  if (pan && gstin.slice(2, 12) !== pan) {
    return "The PAN inside this GSTIN (characters 3 to 12) does not match your PAN.";
  }
  return null;
}

// --- session -----------------------------------------------------------------------------------

/*
 * A session is { accessToken, user }, where user is the object returned by
 * POST /api/v1/auth/login and GET /api/v1/auth/me: { id, email, full_name, role }.
 * role is "business", "ca" or "admin".
 */

/** Each role's area of the app: where it lands after login, and every page URL's prefix. */
export const ROLE_HOME = {
  business: "/business",
  ca: "/ca",
  admin: "/admin",
};

const STORAGE_KEY = "ca-helper.session";

// TODO: move to a refresh-token cookie later. localStorage is readable by any
// script on the page (XSS risk); fine for this prototype, not for production.
// Storage can throw (private mode, blocked site data), so every access is guarded.

export function loadSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Not persisted: the user stays logged in until the page is reloaded.
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing stored, nothing to clear.
  }
}

// --- authRules ---------------------------------------------------------------------------------

/**
 * Zod rules shared by the account forms (signup, verify email, reset and change
 * password). The backend checks the same rules in backend/app/schemas/auth.py.
 */

export const PASSWORD_RULE_TEXT =
  "Use 8 to 128 characters, with at least one letter and one number.";

/** A new password: 8 to 128 characters, at least one letter and one number. */
export const newPasswordSchema = z
  .string()
  .min(8, PASSWORD_RULE_TEXT)
  .max(128, PASSWORD_RULE_TEXT)
  .regex(/[A-Za-z]/, PASSWORD_RULE_TEXT)
  .regex(/[0-9]/, PASSWORD_RULE_TEXT);

/** The 6-digit code from an email (spaces around it are ignored). */
export const codeSchema = z
  .string()
  .trim()
  .regex(/^[0-9]{6}$/, "Enter the 6-digit code from the email.");

export const emailSchema = z.email("Enter a valid email address.");

/** Add to a form schema with `password` and `confirm_password` fields. */
export function passwordsMatch(values) {
  return values.password === values.confirm_password;
}

export const PASSWORDS_MATCH_ERROR = {
  message: "The passwords do not match.",
  path: ["confirm_password"],
};
