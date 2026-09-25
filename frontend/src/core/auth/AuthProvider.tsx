import { useQueryClient } from "@tanstack/react-query";
import type { Middleware } from "openapi-fetch";
import { type ReactNode, useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";

import { api } from "@/core/api/client";

import { AuthContext, type AuthContextValue, LoginError } from "./auth-context";
import { clearSession, loadSession, saveSession, type Session } from "./session";

/**
 * Holds the session (token + user) and connects it to the API client:
 * - every request gets `Authorization: Bearer <token>`;
 * - any 401 on a request that carried a token logs the user out
 *   (expired/invalid token, or the account was deactivated).
 * The route guards (RequireRole) then send the user to /login.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(loadSession);
  // The token the API middleware sends. A ref (updated at once by login/logout),
  // so requests fired right after login already carry the new token.
  const tokenRef = useRef<string | null>(session?.accessToken ?? null);

  const logout = useCallback(() => {
    tokenRef.current = null;
    clearSession();
    setSession(null);
    queryClient.clear(); // never show one user's cached data to the next
  }, [queryClient]);

  // A layout effect, not useEffect: React runs all layout effects before any
  // useEffect, so the middleware is in place before child pages start fetching.
  useLayoutEffect(() => {
    const middleware: Middleware = {
      onRequest({ request }) {
        if (tokenRef.current) request.headers.set("Authorization", `Bearer ${tokenRef.current}`);
        return request;
      },
      onResponse({ request, response }) {
        if (response.status === 401 && request.headers.has("Authorization")) logout();
        return response;
      },
    };
    api.use(middleware);
    return () => api.eject(middleware);
  }, [logout]);

  const login = useCallback(async (email: string, password: string) => {
    const { data, error } = await api.POST("/api/v1/auth/login", { body: { email, password } });
    if (error) {
      throw new LoginError(error.error.code, error.error.message, error.error.request_id);
    }
    const next = { accessToken: data.access_token, user: data.user };
    tokenRef.current = next.accessToken;
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
