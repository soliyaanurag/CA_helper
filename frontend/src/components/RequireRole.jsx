import { Navigate, useLocation } from "react-router";

import { useAuth } from "@/hooks/useAuth";
import { ROLE_HOME } from "@/lib/session";

/**
 * Route guard for an area layout.
 * - Not logged in -> /login (and back here after logging in).
 * - Logged in with another role -> that role's own home.
 * The backend checks the role again on every request; this only keeps users
 * from landing on pages that would fail.
 */
export function RequireRole({ role, children }) {
  const { user } = useAuth();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (user.role !== role) {
    return <Navigate to={ROLE_HOME[user.role]} replace />;
  }
  return children;
}
