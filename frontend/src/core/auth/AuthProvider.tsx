import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { api } from "@/core/api/client";
import { unwrap } from "@/core/api/errors";

import { AuthContext, type AuthContextValue } from "./auth-context";
import { clearSession, loadSession, saveSession } from "./session";

// Called when the API rejects our token; AuthProvider points it at its logout().
let onUnauthorized = () => {};

// Registered once, when this file loads (so before any page fetches anything):
// every request carries the logged-in user's token, and a 401 on a request that
// carried one (expired or invalid token, deactivated account) logs the user out.
api.use({
  onRequest({ request }) {
    const token = loadSession()?.accessToken;
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
  onResponse({ request, response }) {
    if (response.status === 401 && request.headers.has("Authorization")) onUnauthorized();
    return response;
  },
});

/** Holds the logged-in user; the route guards (RequireRole) send everyone else to /login. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState(loadSession);

  const logout = useCallback(() => {
    clearSession();
    setSession(null);
    queryClient.clear(); // never show one user's cached data to the next
  }, [queryClient]);

  useEffect(() => {
    onUnauthorized = logout;
  }, [logout]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await unwrap(api.POST("/api/v1/auth/login", { body: { email, password } }));
    const next = { accessToken: data.access_token, user: data.user };
    saveSession(next);
    setSession(next);
    return data.user;
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user: session?.user ?? null, login, logout }),
    [session, login, logout],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}
