import { createContext, useContext } from "react";

/**
 * The value AuthProvider puts in this context:
 * - user: the logged-in user, or null;
 * - login(email, password): calls the login endpoint and returns the user; throws
 *   ApiRequestError (e.g. code INVALID_CREDENTIALS) on failure;
 * - logout().
 */
export const AuthContext = createContext(null);

/** Current user plus login/logout. Use inside <AuthProvider>. */
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth() must be used inside <AuthProvider>");
  return value;
}
