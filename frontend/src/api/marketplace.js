/**
 * All calls to the marketplace backend (backend/app/routes/marketplace.py).
 * Pages use these functions instead of calling the backend themselves.
 */
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";

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

// --- Engagements (a business working with a CA) ---

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

// --- Pro-bono queue (MA16) ---

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
