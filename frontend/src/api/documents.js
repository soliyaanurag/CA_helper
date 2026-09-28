/**
 * All calls to the documents backend (backend/app/routes/documents.py): the vault and
 * the links between documents and filings. Pages use these functions instead of
 * calling the backend themselves.
 */
import { useQuery } from "@tanstack/react-query";

import { apiDownload, apiFetch } from "@/api/client";

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
