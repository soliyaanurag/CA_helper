import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useLayoutEffect, useMemo, useState } from "react";

import { apiFetch, setAuth } from "@/api/client";
import { AuthContext } from "@/hooks/useAuth";
import { clearSession, loadSession, saveSession } from "@/lib/session";

/**
 * Holds the session (token + user) and hands it to the API client (setAuth), so
 * apiFetch() sends the token with every request and calls logout() on a 401
 * (expired/invalid token, or the account was deactivated).
 * The route guards (RequireRole) then send the user to /login.
 */
export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState(loadSession);

  const logout = useCallback(() => {
    clearSession();
    setSession(null);
    queryClient.clear(); // never show one user's cached data to the next
  }, [queryClient]);

  // A layout effect, not useEffect: React runs all layout effects before any
  // useEffect, so the token is in place before pages start fetching.
  useLayoutEffect(() => {
    setAuth(session?.accessToken ?? null, logout);
  }, [session, logout]);

  const login = useCallback(async (email, password) => {
    const data = await apiFetch("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
    });
    const next = { accessToken: data.access_token, user: data.user };
    saveSession(next);
    setSession(next);
    return data.user;
  }, []);

  const value = useMemo(
    () => ({ user: session?.user ?? null, login, logout }),
    [session, login, logout],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}
