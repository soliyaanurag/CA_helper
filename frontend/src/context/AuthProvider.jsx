import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useLayoutEffect, useMemo, useState } from "react";

import { acceptTerms as sendAcceptTerms } from "@/api/auth";
import { apiFetch, setAuth } from "@/api/client";
import { AuthContext } from "@/hooks/useAuth";
import { clearSession, loadSession, saveSession } from "@/lib/session";

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
