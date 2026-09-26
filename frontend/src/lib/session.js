/*
 * A session is { accessToken, user }, where user is the object returned by
 * POST /api/v1/auth/login and GET /api/v1/auth/me: { id, email, full_name, role }.
 * role is "business", "ca" or "admin".
 */

/** Each role's area of the app: where it lands after login, and every page URL's prefix. */
export const ROLE_HOME = {
  business: "/business",
  ca: "/ca",
  admin: "/admin",
};

const STORAGE_KEY = "ca-helper.session";

// TODO: move to a refresh-token cookie later. localStorage is readable by any
// script on the page (XSS risk); fine for this prototype, not for production.
// Storage can throw (private mode, blocked site data), so every access is guarded.

export function loadSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Not persisted: the user stays logged in until the page is reloaded.
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing stored, nothing to clear.
  }
}
