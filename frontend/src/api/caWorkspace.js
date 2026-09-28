/**
 * API calls for the ca_workspace module (backend/app/routes/ca_workspace.py): the CA's
 * clients, a client's workspace, the batch view, document requests and "mark filed".
 * Every call goes through apiFetch(), so failures are ApiRequestError (code, message).
 */
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";

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

// --- The business side: its CAs' open requests (to-dos) ----------------------------

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
