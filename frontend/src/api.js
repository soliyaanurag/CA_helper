import { useQuery } from "@tanstack/react-query";

// --- client ------------------------------------------------------------------------------------

/**
 * apiFetch(): the one way the frontend calls the backend.
 *
 *   apiFetch("/api/v1/compliance/dashboard")
 *   apiFetch("/api/v1/auth/login", { method: "POST", body: { email, password } })
 *
 * - Every URL is the full path ("/api/v1/..."). The Vite dev server forwards /api
 *   to Flask, so requests go to the page's own origin.
 * - Sends `body` as JSON (a FormData body, for file uploads, as it is) and returns the
 *   parsed JSON response (null if there is none). apiDownload() gets a file instead.
 * - Adds `Authorization: Bearer <token>` while someone is logged in.
 * - Throws ApiRequestError (status, code, message) for every error response.
 * - A 401 on a request that carried a token logs the user out (the token expired or
 *   the account no longer exists).
 * - A request with no answer after REQUEST_TIMEOUT_MS fails with code TIMEOUT, so a
 *   hung server shows a clear message instead of a page that never finishes.
 *
 * Usage, in the hooks below:
 *   queryFn: () => apiFetch("/api/v1/<module>/<resource>"),
 */

/**
 * A failed API call, carrying the standard error body { error: { code, message } }:
 * switch on `code` (e.g. "INVALID_CREDENTIALS") and show `message`.
 */
export class ApiRequestError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

// How long a request may take before it fails with code TIMEOUT.
export const REQUEST_TIMEOUT_MS = 20_000;

// The logged-in user's token and how to log them out. AuthProvider
// (auth.jsx) sets both through setAuth() whenever the session changes.
let accessToken = null;
let logout = () => {};

export function setAuth(token, logoutFunction) {
  accessToken = token;
  logout = logoutFunction;
}

export async function apiFetch(path, { method = "GET", body } = {}) {
  const headers = {};
  const isForm = body instanceof FormData; // a file upload: the browser sets the type
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response;
  let data;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined || isForm ? body : JSON.stringify(body),
      signal: controller.signal,
    });
    // No body (204) or not JSON (e.g. a proxy's HTML error page): null.
    data = await response.json().catch(() => null);
  } catch (error) {
    if (!controller.signal.aborted) throw error; // a network failure: see errorMessage()
  } finally {
    clearTimeout(timer);
  }
  if (controller.signal.aborted) {
    throw new ApiRequestError(
      0,
      "TIMEOUT",
      "The server did not answer within 20 seconds. Try again in a moment.",
    );
  }
  if (response.ok) return data;

  if (response.status === 401 && headers.Authorization) logout();
  const error = data?.error; // the standard error body: {error: {code, message}}
  throw new ApiRequestError(
    response.status,
    error?.code ?? "HTTP_ERROR",
    error?.message ?? `The server answered ${response.status}.`,
  );
}

/**
 * Downloads a file the API sends (e.g. an admin opening a CA's certificate) as a Blob.
 * Throws ApiRequestError like apiFetch() when the API answers with an error.
 */
export async function apiDownload(path) {
  const response = await fetch(path, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
  if (response.ok) return response.blob();
  const data = await response.json().catch(() => null);
  if (response.status === 401 && accessToken) logout();
  throw new ApiRequestError(
    response.status,
    data?.error?.code ?? "HTTP_ERROR",
    data?.error?.message ?? `The server answered ${response.status}.`,
  );
}

/** Text to show for any error thrown by a query: the API's message, or a network hint. */
export function errorMessage(error) {
  if (error instanceof ApiRequestError) return error.message;
  return "Cannot reach the server. Check your connection and try again.";
}

// --- health ------------------------------------------------------------------------------------

/**
 * GET /api/health: is the backend up, and can it reach its database?
 * 200 -> {status: "ok", database: "ok"}; 503 -> {status: "degraded", database: "unavailable"}
 * (the API answers, but the database is down). Only a failed request is an error.
 * Plain fetch, not apiFetch(): the 503 body is data to show, not the standard error body.
 */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const response = await fetch("/api/health");
      if (response.ok || response.status === 503) return response.json();
      throw new Error(`API returned HTTP ${response.status}`);
    },
    retry: false,
  });
}

// --- auth --------------------------------------------------------------------------------------

/**
 * API calls for accounts (backend/app/auth.py): signup, email verification
 * and passwords. Login itself is in auth.jsx, because it changes
 * the session. Every call goes through apiFetch(), so a failure throws
 * ApiRequestError (code, message). Endpoints that answer 204 resolve to null.
 */

function post(path, body) {
  return apiFetch(path, { method: "POST", body });
}

/** POST /api/v1/auth/signup {full_name, email, password, role} -> the new (unverified) user */
export function signup({ full_name, email, password, role }) {
  // Signing up is only possible after ticking "I agree to the Terms and Privacy Policy".
  return post("/api/v1/auth/signup", { full_name, email, password, role, terms_accepted: true });
}

/** POST /api/v1/auth/verify-email: the 6-digit code emailed at signup */
export function verifyEmail(email, code) {
  return post("/api/v1/auth/verify-email", { email, code });
}

/** POST /api/v1/auth/verify-email/resend: emails a new code */
export function resendVerificationCode(email) {
  return post("/api/v1/auth/verify-email/resend", { email });
}

/** POST /api/v1/auth/forgot-password: emails a reset code */
export function forgotPassword(email) {
  return post("/api/v1/auth/forgot-password", { email });
}

/** POST /api/v1/auth/reset-password: sets a new password with the emailed code */
export function resetPassword(email, code, newPassword) {
  return post("/api/v1/auth/reset-password", { email, code, new_password: newPassword });
}

/** POST /api/v1/auth/change-password: for the logged-in user */
export function changePassword(currentPassword, newPassword) {
  return post("/api/v1/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export const SETTINGS_KEY = ["auth", "settings"];

/** GET /api/v1/auth/settings: { email_notifications } */
export function useSettings() {
  return useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: () => apiFetch("/api/v1/auth/settings"),
  });
}

/** PUT /api/v1/auth/settings: switch the notification emails on or off; returns the settings */
export function saveSettings(emailNotifications) {
  return apiFetch("/api/v1/auth/settings", {
    method: "PUT",
    body: { email_notifications: emailNotifications },
  });
}

// --- onboarding --------------------------------------------------------------------------------

/**
 * All calls to the onboarding backend (backend/app/onboarding.py).
 * Pages use these functions instead of calling the backend themselves.
 */

// Name of the business in the query cache. OnboardingPage fills it after registering.
export const MY_BUSINESS_KEY = ["onboarding", "business"];

// Asks the backend for the logged-in user's business and its regulatory profile:
// { business, profile }. Returns null if the business is not registered yet (404).
async function fetchMyBusiness() {
  try {
    return await apiFetch("/api/v1/onboarding/business");
  } catch (error) {
    if (error.code === "BUSINESS_NOT_FOUND") {
      return null;
    }
    throw error;
  }
}

// Used by OnboardingPage.
export function useMyBusiness() {
  return useQuery({ queryKey: MY_BUSINESS_KEY, queryFn: fetchMyBusiness });
}

// Registers the business (once). The backend also works out the regulatory profile
// and creates the filings. Returns { business, profile }.
export function registerBusiness(form) {
  return apiFetch("/api/v1/onboarding/business", { method: "POST", body: form });
}

// Edits the business. The backend recomputes the profile and syncs this year's filings.
// Returns { business, profile, changes: { profile: [{line, old, new}], filings: {...} } }.
export function updateBusiness(form) {
  return apiFetch("/api/v1/onboarding/business", { method: "PUT", body: form });
}

// Up to 3 suggested NIC activity codes for the business's description (nothing is saved):
// { picks: [{code, description, reason, source: "ai" | "keywords"}], shortlist, ai_used }.
export function suggestNicCodes() {
  return apiFetch("/api/v1/onboarding/nic-suggestions", { method: "POST" });
}

// Searches the official NIC list by code or words (for choosing a code by hand).
// Only runs once at least 2 characters are typed.
export function useNicSearch(query) {
  const text = query.trim();
  return useQuery({
    queryKey: ["onboarding", "nic-codes", text],
    queryFn: () => apiFetch("/api/v1/onboarding/nic-codes?q=" + encodeURIComponent(text)),
    enabled: text.length >= 2,
  });
}

// Saves the NIC code the user confirmed. Returns { code, description }.
export function saveNicCode(code) {
  return apiFetch("/api/v1/onboarding/business/nic-code", { method: "PUT", body: { code } });
}

// The states and union territories with their GST codes, for the form's dropdown.
export function useGstStates() {
  return useQuery({
    queryKey: ["onboarding", "states"],
    queryFn: () => apiFetch("/api/v1/onboarding/states"),
    staleTime: Infinity, // reference data: it does not change while the app is open
  });
}

// Reads a GST certificate or PAN card on the server (locally, never stored) and
// returns what it found: { found: { pan?, gstin?, legal_name?, state?, entity_type? } }.
export function readRegistrationDocument(file) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch("/api/v1/onboarding/autofill", { method: "POST", body: form });
}

// --- compliance --------------------------------------------------------------------------------

/**
 * All calls to the compliance backend (backend/app/compliance.py).
 * Pages use these functions instead of calling the backend themselves.
 */

// Name of the filings list in the query cache. OnboardingPage refreshes it after registering.
export const FILINGS_KEY = ["compliance", "items"];

/** GET /api/v1/compliance/dashboard */
export function useComplianceDashboard() {
  return useQuery({
    queryKey: ["compliance", "dashboard"],
    queryFn: () => apiFetch("/api/v1/compliance/dashboard"),
  });
}

// The business's filings, soonest due first.
// Returns null if the business is not registered yet (the backend answers 404).
async function fetchFilings() {
  try {
    return await apiFetch("/api/v1/compliance/items");
  } catch (error) {
    if (error.code === "BUSINESS_NOT_FOUND") {
      return null;
    }
    throw error;
  }
}

// Used by CompliancePage.
export function useFilings() {
  return useQuery({ queryKey: FILINGS_KEY, queryFn: fetchFilings });
}

// --- One filing's page ---------------------------------------------------------------------

// Name of one filing in the query cache. The actions below return the updated filing,
// and FilingPage puts it there.
export function filingKey(itemId) {
  return ["compliance", "item", itemId];
}

// { filing, form_name, content_status, explanation, instructions, checklist, acknowledgement }
export function useFiling(itemId) {
  return useQuery({
    queryKey: filingKey(itemId),
    queryFn: () => apiFetch("/api/v1/compliance/items/" + itemId),
  });
}

// path is "self" (file it myself) or "ca" (with a CA).
export function chooseFilingPath(itemId, path) {
  return apiFetch("/api/v1/compliance/items/" + itemId + "/path", {
    method: "POST",
    body: { path },
  });
}

// Tick (ticked = true) or untick one document of the checklist.
export function tickChecklist(itemId, key, ticked) {
  return apiFetch("/api/v1/compliance/items/" + itemId + "/checklist", {
    method: "POST",
    body: { key, ticked },
  });
}

// "I filed it myself". Both the ARN and the file are optional.
export function markFiled(itemId, acknowledgementNo, file) {
  const form = new FormData();
  if (acknowledgementNo) form.append("acknowledgement_no", acknowledgementNo);
  if (file) form.append("file", file);
  return apiFetch("/api/v1/compliance/items/" + itemId + "/mark-filed", {
    method: "POST",
    body: form,
  });
}

// Undo a mistaken "mark as filed".
export function unmarkFiled(itemId) {
  return apiFetch("/api/v1/compliance/items/" + itemId + "/unmark-filed", { method: "POST" });
}

// The uploaded acknowledgement file (a Blob), loaded only when there is one.
export function useAcknowledgementFile(itemId, enabled) {
  return useQuery({
    queryKey: [...filingKey(itemId), "acknowledgement"],
    queryFn: () => apiDownload("/api/v1/compliance/items/" + itemId + "/acknowledgement"),
    enabled,
  });
}

/**
 * GET /api/v1/compliance/items/<id>/peer-insights: how similar businesses file this form.
 * { scope: "segment" | "overall" | "none", entity_type, msme_tier, min_businesses,
 *   business_count, filing_count, self: { count, share_pct, on_time_pct }, ca: {...} }
 */
export function usePeerInsights(itemId) {
  return useQuery({
    queryKey: [...filingKey(itemId), "peers"],
    queryFn: () => apiFetch("/api/v1/compliance/items/" + itemId + "/peer-insights"),
  });
}

// --- documents ---------------------------------------------------------------------------------

/**
 * All calls to the documents backend (backend/app/documents.py): the vault and
 * the links between documents and filings. Pages use these functions instead of
 * calling the backend themselves.
 */

// The types a business can upload (every documents.doc_type but a CA's certificate).
export const UPLOAD_TYPES = [
  "gst_certificate",
  "pan_card",
  "sales_register",
  "purchase_register",
  "bank_statement",
  "invoice",
  "salary_register",
  "tds_challan",
  "acknowledgement",
  "other",
];

// Every documents list in the query cache starts with this; refresh it after a change.
export const DOCUMENTS_KEY = ["documents"];

// The query string of a list request, without the empty filters.
function listPath(params) {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value !== "" && value !== null && value !== undefined) query.set(name, value);
  }
  return "/api/v1/documents?" + query.toString();
}

/**
 * GET /api/v1/documents: { items, page, page_size, total }, newest first.
 * params: { fy, doc_type, compliance_item_id, page, page_size } (all optional).
 * Each item: { id, doc_type, original_filename, mime_type, size_bytes, fy, period_label,
 * ocr_status, created_at, links: [{ id, compliance_item_id, form_code, period_label,
 * checklist_key }], acknowledgement_of: [{ compliance_item_id, form_code, period_label }] }
 */
export function useDocuments(params, enabled = true) {
  return useQuery({
    queryKey: [...DOCUMENTS_KEY, params],
    queryFn: () => apiFetch(listPath(params)),
    enabled,
  });
}

/**
 * Upload a file. fields: { doc_type, fy, period_label, compliance_item_id, checklist_key };
 * only doc_type is needed. With compliance_item_id the file is also linked to that filing.
 */
export function uploadDocument(file, fields) {
  const form = new FormData();
  form.append("file", file);
  for (const [name, value] of Object.entries(fields)) {
    if (value) form.append(name, value);
  }
  return apiFetch("/api/v1/documents", { method: "POST", body: form });
}

// Soft delete. Fails with DOCUMENT_IN_USE for the proof of a filed filing.
export function deleteDocument(documentId) {
  return apiFetch("/api/v1/documents/" + documentId, { method: "DELETE" });
}

// Link a vault file to a filing's checklist entry ("general" for none); ticks the entry.
export function linkDocument(documentId, complianceItemId, checklistKey) {
  return apiFetch("/api/v1/documents/" + documentId + "/links", {
    method: "POST",
    body: { compliance_item_id: complianceItemId, checklist_key: checklistKey },
  });
}

// Remove one link (its id is in the document's `links`).
export function unlinkDocument(linkId) {
  return apiFetch("/api/v1/documents/links/" + linkId, { method: "DELETE" });
}

// Download the file and save it under its own name.
export async function downloadDocument(document) {
  const blob = await apiDownload("/api/v1/documents/" + document.id + "/file");
  const href = URL.createObjectURL(blob);
  const anchor = window.document.createElement("a");
  anchor.href = href;
  anchor.download = document.original_filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(href), 60_000); // after the browser has read it
}

// --- alerts ------------------------------------------------------------------------------------

/**
 * All calls to the alerts backend (backend/app/alerts.py): the notification
 * tray, email settings and the penalty estimator.
 * Pages use these functions instead of calling the backend themselves.
 */

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

// --- Penalty estimates ---------------------------------------------------------------------

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

// --- marketplace -------------------------------------------------------------------------------

/**
 * All calls to the marketplace backend (backend/app/marketplace.py).
 * Pages use these functions instead of calling the backend themselves.
 */

// Name of the saved CA profile in the query cache. CaProfilePage updates it after a save.
export const CA_PROFILE_KEY = ["marketplace", "ca-profile"];

// Asks the backend for the logged-in CA's profile.
// Returns null if the CA has not saved a profile yet (the backend answers 404).
async function fetchCaProfile() {
  try {
    return await apiFetch("/api/v1/marketplace/ca-profile");
  } catch (error) {
    if (error.code === "CA_PROFILE_NOT_FOUND") {
      return null;
    }
    throw error;
  }
}

// Used by CaProfilePage and CaDashboardPage.
export function useCaProfile() {
  return useQuery({ queryKey: CA_PROFILE_KEY, queryFn: fetchCaProfile });
}

// Saves the CA's profile form. Returns the saved profile.
export function saveCaProfile(profile) {
  return apiFetch("/api/v1/marketplace/ca-profile", { method: "PUT", body: profile });
}

// Uploads the Certificate of Practice (a PDF, JPG or PNG File). Returns the saved profile,
// now waiting for an admin check.
export function uploadCertificate(file) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch("/api/v1/marketplace/ca-profile/certificate", { method: "POST", body: form });
}

// The list of verified CAs for the "Find a CA" page.
// filters = { specialization, language, city, service, page }; empty filters are not sent.
// With a service chosen, each CA in the list has their `price` for it.
export function useVerifiedCas(filters) {
  const params = new URLSearchParams();
  if (filters.specialization) params.set("specialization", filters.specialization);
  if (filters.language) params.set("language", filters.language);
  if (filters.city) params.set("city", filters.city);
  if (filters.service) params.set("service", filters.service);
  if (filters.page > 1) params.set("page", filters.page);

  let url = "/api/v1/marketplace/cas";
  if (params.toString()) {
    url = url + "?" + params.toString();
  }

  return useQuery({
    queryKey: ["marketplace", "cas", url],
    queryFn: () => apiFetch(url),
  });
}

// One verified CA's page: details plus the services they offer, each with the CA's
// price and the typical range. A CA businesses may not see answers 404 CA_NOT_FOUND.
export function useVerifiedCa(caId) {
  return useQuery({
    queryKey: ["marketplace", "ca", caId],
    queryFn: () => apiFetch("/api/v1/marketplace/cas/" + caId),
  });
}

// Every catalog service with its typical price range (min / median / max).
// Used by the "Services & prices", "Find a CA" and "Typical fees" pages.
export function useServices() {
  return useQuery({
    queryKey: ["marketplace", "services"],
    queryFn: () => apiFetch("/api/v1/marketplace/services"),
  });
}

// Name of the CA's price menu in the query cache. CaServicesPage updates it after a save.
export const CA_SERVICES_KEY = ["marketplace", "ca-services"];

// The services the logged-in CA offers: { items: [{ service_id, price }] }.
export function useCaServices() {
  return useQuery({
    queryKey: CA_SERVICES_KEY,
    queryFn: () => apiFetch("/api/v1/marketplace/ca-services"),
  });
}

// Saves the CA's whole price menu (it replaces the old one). Returns the saved menu.
export function saveCaServices(items) {
  return apiFetch("/api/v1/marketplace/ca-services", { method: "PUT", body: { items } });
}

// --- Engagements (a business working with a CA) --------------------------------------------

// Names in the query cache. Pages refresh them after an action.
export const MY_ENGAGEMENTS_KEY = ["marketplace", "my-engagements"];
export const CA_ENGAGEMENTS_KEY = ["marketplace", "ca-engagements"];

// The business's filings with this CA's prices, for the "Request this CA" page.
// Returns null if the business is not registered yet (the backend answers 404).
async function fetchRequestableFilings(caId) {
  try {
    return await apiFetch("/api/v1/marketplace/cas/" + caId + "/requestable-filings");
  } catch (error) {
    if (error.code === "BUSINESS_NOT_FOUND") {
      return null;
    }
    throw error;
  }
}

export function useRequestableFilings(caId) {
  return useQuery({
    queryKey: ["marketplace", "requestable-filings", caId],
    queryFn: () => fetchRequestableFilings(caId),
  });
}

// Sends a request to a CA. items = [{ compliance_item_id, service_id }].
export function sendRequest(caId, items) {
  return apiFetch("/api/v1/marketplace/engagements", {
    method: "POST",
    body: { ca_profile_id: caId, items },
  });
}

// The business's engagements, newest first. Null if the business is not registered yet.
async function fetchMyEngagements() {
  try {
    return await apiFetch("/api/v1/marketplace/my-engagements");
  } catch (error) {
    if (error.code === "BUSINESS_NOT_FOUND") {
      return null;
    }
    throw error;
  }
}

export function useMyEngagements() {
  return useQuery({ queryKey: MY_ENGAGEMENTS_KEY, queryFn: fetchMyEngagements });
}

// The CA's engagements, newest first.
export function useCaEngagements() {
  return useQuery({
    queryKey: CA_ENGAGEMENTS_KEY,
    queryFn: () => apiFetch("/api/v1/marketplace/ca-engagements"),
  });
}

// One action on an engagement, e.g. engagementAction(id, "accept") or
// engagementAction(id, "quote", { reason, prices }). Returns the updated engagement.
export function engagementAction(engagementId, action, body) {
  return apiFetch("/api/v1/marketplace/engagements/" + engagementId + "/" + action, {
    method: "POST",
    body,
  });
}

// --- Pro-bono queue ------------------------------------------------------------------------

export const PRO_BONO_KEY = ["marketplace", "pro-bono"];
export const PRO_BONO_QUEUE_KEY = ["marketplace", "pro-bono-queue"];

// The business's pro-bono page: { eligible, reason, request, filings }.
// Returns null if the business is not registered yet (the backend answers 404).
async function fetchProBonoPage() {
  try {
    return await apiFetch("/api/v1/marketplace/pro-bono");
  } catch (error) {
    if (error.code === "BUSINESS_NOT_FOUND") {
      return null;
    }
    throw error;
  }
}

export function useProBonoPage() {
  return useQuery({ queryKey: PRO_BONO_KEY, queryFn: fetchProBonoPage });
}

// The business joins the queue with some filings and a short note.
export function joinProBonoQueue(filingIds, note) {
  return apiFetch("/api/v1/marketplace/pro-bono", {
    method: "POST",
    body: { compliance_item_ids: filingIds, note: note },
  });
}

// The business leaves the queue.
export function cancelProBonoRequest(requestId) {
  return apiFetch("/api/v1/marketplace/pro-bono/" + requestId + "/cancel", { method: "POST" });
}

// The CA's pro-bono page: { pledged, used_this_month, verified, requests }.
export function useProBonoQueue() {
  return useQuery({
    queryKey: PRO_BONO_QUEUE_KEY,
    queryFn: () => apiFetch("/api/v1/marketplace/pro-bono-queue"),
  });
}

// The CA takes a request from the queue (a free engagement starts at once).
export function acceptProBonoRequest(requestId) {
  return apiFetch("/api/v1/marketplace/pro-bono/" + requestId + "/accept", { method: "POST" });
}

// --- caWorkspace -------------------------------------------------------------------------------

/**
 * API calls for the ca_workspace module (backend/app/ca_workspace.py): the CA's
 * clients, a client's workspace, the batch view, document requests and "mark filed".
 * Every call goes through apiFetch(), so failures are ApiRequestError (code, message).
 */

// Every ca_workspace query in the cache starts with this; refresh it after a change.
export const CA_WORKSPACE_KEY = ["ca_workspace"];

/** GET /api/v1/ca-workspace/dashboard */
export function useCaDashboard() {
  return useQuery({
    queryKey: [...CA_WORKSPACE_KEY, "dashboard"],
    queryFn: () => apiFetch("/api/v1/ca-workspace/dashboard"),
  });
}

/**
 * GET /api/v1/ca-workspace/clients: the CA's clients, most urgent first.
 * Each: { business_id, business_name, filing_count, open_filing_count, open_request_count,
 * next_deadline, overdue_count, missing_documents, score, reasons: [{ reason, points }] }
 */
export function useCaClients() {
  return useQuery({
    queryKey: [...CA_WORKSPACE_KEY, "clients"],
    queryFn: () => apiFetch("/api/v1/ca-workspace/clients"),
  });
}

/**
 * GET /api/v1/ca-workspace/clients/<id>: { business, profile, filings: [{ filing,
 * checklist, documents: [{ document_id, original_filename, doc_type, size_bytes,
 * created_at, checklist_key }], open_requests }] }
 */
export function useCaClient(businessId) {
  return useQuery({
    queryKey: [...CA_WORKSPACE_KEY, "client", businessId],
    queryFn: () => apiFetch("/api/v1/ca-workspace/clients/" + businessId),
  });
}

/**
 * GET /api/v1/ca-workspace/batches: [{ form_code, due_date, ready_count, filings:
 * [{ business_id, business_name, compliance_item_id, period_label, status,
 * required_total, required_ready, missing, ready }] }], soonest first.
 */
export function useCaBatches() {
  return useQuery({
    queryKey: [...CA_WORKSPACE_KEY, "batches"],
    queryFn: () => apiFetch("/api/v1/ca-workspace/batches"),
  });
}

// The CA asks the client for a document for one filing ("general" for no checklist entry).
export function createDocumentRequest(businessId, complianceItemId, checklistKey, message) {
  return apiFetch("/api/v1/ca-workspace/clients/" + businessId + "/document-requests", {
    method: "POST",
    body: { compliance_item_id: complianceItemId, checklist_key: checklistKey, message },
  });
}

export function cancelDocumentRequest(requestId) {
  return apiFetch("/api/v1/ca-workspace/document-requests/" + requestId + "/cancel", {
    method: "POST",
  });
}

// The CA filed one filing. Both the ARN and the file are optional.
export function caMarkFiled(businessId, itemId, acknowledgementNo, file) {
  const form = new FormData();
  if (acknowledgementNo) form.append("acknowledgement_no", acknowledgementNo);
  if (file) form.append("file", file);
  return apiFetch(
    "/api/v1/ca-workspace/clients/" + businessId + "/filings/" + itemId + "/mark-filed",
    { method: "POST", body: form },
  );
}

// --- The business side: its CAs' open requests (to-dos) ------------------------------------

/**
 * GET /api/v1/ca-workspace/document-requests[?compliance_item_id=]: the business's open
 * requests, oldest first: [{ id, compliance_item_id, form_code, period_label,
 * checklist_key, message, status, created_at, ca_name, ... }]
 */
export function useMyDocumentRequests(itemId) {
  const query = itemId ? "?compliance_item_id=" + itemId : "";
  return useQuery({
    queryKey: [...CA_WORKSPACE_KEY, "my-requests", itemId ?? "all"],
    queryFn: () => apiFetch("/api/v1/ca-workspace/document-requests" + query),
  });
}

// Answer a request with a document already in the vault (upload it first if needed).
export function fulfilDocumentRequest(requestId, documentId) {
  return apiFetch("/api/v1/ca-workspace/document-requests/" + requestId + "/fulfil", {
    method: "POST",
    body: { document_id: documentId },
  });
}

// --- regulatory --------------------------------------------------------------------------------

// Names in the query cache; the pages refresh them after an action.
export const REGULATORY_CHANGES_KEY = ["regulatory", "changes"];
export const NEWS_SOURCES_KEY = ["regulatory", "sources"];

// A change found in the news: { id, change_type, summary, form_codes,
// affected_categories, dates, created_at, notified_at, article_title, article_url,
// published_at, source_name, match_count }. affected_categories.extracted_by is
// "keywords" when Gemini did not read the article (then nobody was told).

// Business and CA: the changes about my forms, newest first.
export function useRegulatoryUpdates() {
  return useQuery({
    queryKey: ["regulatory", "updates"],
    queryFn: () => apiFetch("/api/v1/regulatory/updates"),
  });
}

// Admin: every change found in the news, newest first.
export function useRegulatoryChanges() {
  return useQuery({
    queryKey: REGULATORY_CHANGES_KEY,
    queryFn: () => apiFetch("/api/v1/admin/regulatory/changes"),
  });
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

// --- assistant ---------------------------------------------------------------------------------

/**
 * All calls to the AI assistant backend (backend/app/assistant.py).
 * Pages use these functions instead of calling the backend themselves.
 */

// Name of the conversation in the query cache; AssistantChat refreshes it after each question.
export const ASSISTANT_HISTORY_KEY = ["assistant", "history"];

// The user's questions and answers, oldest first:
// [{ id, role: "user" | "assistant", content, citations, ask_a_ca, ai_used, created_at }].
export function useAssistantHistory() {
  return useQuery({
    queryKey: ASSISTANT_HISTORY_KEY,
    queryFn: () => apiFetch("/api/v1/assistant/history"),
  });
}

// Ask a question: { answer, citations: [{ number, title, url, source_path, excerpt }],
// ask_a_ca, ai_used }. The answer is also saved in the history.
export function askAssistant(question) {
  return apiFetch("/api/v1/assistant/ask", { method: "POST", body: { question } });
}

// Clear the conversation.
export function clearAssistantHistory() {
  return apiFetch("/api/v1/assistant/history", { method: "DELETE" });
}

// --- admin -------------------------------------------------------------------------------------

/**
 * API calls for the admin module: TanStack Query hooks around the API client.
 * Every call goes through apiFetch(), so failures are ApiRequestError (code, message).
 */

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
