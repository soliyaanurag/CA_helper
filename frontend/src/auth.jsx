import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useState } from "react";

import { acceptTerms as sendAcceptTerms, apiFetch, setAuth } from "@/api";
import { clearSession, loadSession, saveSession } from "@/lib";

// --- AuthProvider ------------------------------------------------------------------------------

/**
 * Holds the session (token + user) and hands it to the API client (setAuth), so
 * apiFetch() sends the token with every request and ends the session on a 401
 * (expired/invalid token, or the account was deactivated).
 * The route guards (RequireRole) then send the user to /login: after an expired
 * session they remember the page for the next login, after the Log out button they
 * do not (`loggedOutOnPurpose`).
 */
export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState(loadSession);
  const [loggedOutOnPurpose, setLoggedOutOnPurpose] = useState(false);

  const endSession = useCallback(() => {
    clearSession();
    setSession(null);
    queryClient.clear(); // never show one user's cached data to the next
  }, [queryClient]);

  const logout = useCallback(() => {
    setLoggedOutOnPurpose(true);
    endSession();
  }, [endSession]);

  // A layout effect, not useEffect: React runs all layout effects before any
  // useEffect, so the token is in place before pages start fetching.
  useLayoutEffect(() => {
    setAuth(session?.accessToken ?? null, endSession);
  }, [session, endSession]);

  const login = useCallback(async (email, password) => {
    const data = await apiFetch("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
    });
    // termsAccepted: false for a user who signed up before consent was asked (asked once).
    const next = {
      accessToken: data.access_token,
      user: data.user,
      termsAccepted: data.terms_accepted,
    };
    saveSession(next);
    setLoggedOutOnPurpose(false);
    setSession(next);
    return data.user;
  }, []);

  const acceptTerms = useCallback(async () => {
    await sendAcceptTerms();
    const next = { ...loadSession(), termsAccepted: true };
    saveSession(next);
    setSession(next);
  }, []);

  const value = useMemo(
    () => ({
      user: session?.user ?? null,
      termsAccepted: session?.termsAccepted,
      login,
      logout,
      acceptTerms,
      loggedOutOnPurpose,
    }),
    [session, login, logout, acceptTerms, loggedOutOnPurpose],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

// --- useAuth -----------------------------------------------------------------------------------

/**
 * The value AuthProvider puts in this context:
 * - user: the logged-in user, or null;
 * - login(email, password): calls the login endpoint and returns the user; throws
 *   ApiRequestError (e.g. code INVALID_CREDENTIALS) on failure;
 * - logout(): the Log out button;
 * - termsAccepted: false for a user who signed up before consent was asked (then
 *   RequireRole shows the consent step once); acceptTerms() records it;
 * - loggedOutOnPurpose: true after logout() until the next login (the route guard
 *   then does not remember the page for the next login).
 */
export const AuthContext = createContext(null);

/** Current user plus login/logout. Use inside <AuthProvider>. */
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth() must be used inside <AuthProvider>");
  return value;
}
