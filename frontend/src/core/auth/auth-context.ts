import { createContext, useContext } from "react";

import type { User } from "./session";

export interface AuthContextValue {
  /** The logged-in user, or null. */
  user: User | null;
  /** Calls the login endpoint; throws LoginError with the API's error code on failure. */
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

/** A failed login. `code` is the API error code (INVALID_CREDENTIALS, ACCOUNT_INACTIVE, ...). */
export class LoginError extends Error {
  code: string;
  requestId?: string;

  constructor(code: string, message: string, requestId?: string) {
    super(message);
    this.code = code;
    this.requestId = requestId;
  }
}
