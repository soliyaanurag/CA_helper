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
