import type { components } from "@/core/api/generated/schema";

/** The logged-in user as returned by POST /api/v1/auth/login and GET /api/v1/auth/me. */
export type User = components["schemas"]["User"];
export type Role = User["role"];

export interface Session {
  accessToken: string;
  user: User;
}

/** Where each role lands after login, and where a wrong-role visit is sent back to. */
export const ROLE_HOME: Record<Role, string> = {
  business: "/business",
  ca: "/ca",
  admin: "/admin",
};

const STORAGE_KEY = "ca-helper.session";

// TODO: move to a refresh-token cookie later. localStorage is readable by any
// script on the page (XSS risk); fine for this prototype, not for production.
// Storage can throw (private mode, blocked site data), so every access is guarded.

function readStoredSession(): Session | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

// The current session, kept in memory and copied to localStorage (to survive a reload).
let current: Session | null = readStoredSession();

export function loadSession(): Session | null {
  return current;
}

export function saveSession(session: Session): void {
  current = session;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Not persisted: the user stays logged in until the page is reloaded.
  }
}

export function clearSession(): void {
  current = null;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing stored, nothing to clear.
  }
}
