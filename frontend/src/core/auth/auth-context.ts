import { createContext, useContext } from "react";

import type { User } from "./session";

export interface AuthContextValue {
  /** The logged-in user, or null. */
  user: User | null;
  /** Calls the login endpoint; throws ApiRequestError (e.g. code INVALID_CREDENTIALS) on failure. */
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

/** Current user plus login/logout. Use inside <AuthProvider>. */
export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth() must be used inside <AuthProvider>");
  return value;
}
