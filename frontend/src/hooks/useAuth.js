import { createContext, useContext } from "react";

/**
 * The value AuthProvider puts in this context:
 * - user: the logged-in user, or null;
 * - login(email, password): calls the login endpoint and returns the user; throws
 *   ApiRequestError (e.g. code INVALID_CREDENTIALS) on failure;
 * - logout(): the Log out button;
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
