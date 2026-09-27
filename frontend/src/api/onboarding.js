/**
 * All calls to the onboarding backend (backend/app/routes/onboarding.py).
 * Pages use these functions instead of calling the backend themselves.
 */
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/api/client";

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

// The states and union territories with their GST codes, for the form's dropdown.
export function useGstStates() {
  return useQuery({
    queryKey: ["onboarding", "states"],
    queryFn: () => apiFetch("/api/v1/onboarding/states"),
    staleTime: Infinity, // reference data: it does not change while the app is open
  });
}
