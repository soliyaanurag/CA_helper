/**
 * API calls for accounts (backend/app/routes/auth.py): signup, email verification
 * and passwords. Login itself is in context/AuthProvider.jsx, because it changes
 * the session. Every call goes through apiFetch(), so a failure throws
 * ApiRequestError (code, message). Endpoints that answer 204 resolve to null.
 */
import { apiFetch } from "@/api/client";

function post(path, body) {
  return apiFetch(path, { method: "POST", body });
}

/** POST /api/v1/auth/signup {full_name, email, password, role} -> the new (unverified) user */
export function signup({ full_name, email, password, role }) {
  return post("/api/v1/auth/signup", { full_name, email, password, role });
}

/** POST /api/v1/auth/verify-email: the 6-digit code emailed at signup */
export function verifyEmail(email, code) {
  return post("/api/v1/auth/verify-email", { email, code });
}

/** POST /api/v1/auth/verify-email/resend: emails a new code (at most one a minute) */
export function resendVerificationCode(email) {
  return post("/api/v1/auth/verify-email/resend", { email });
}

/** POST /api/v1/auth/forgot-password: emails a reset code (at most one a minute) */
export function forgotPassword(email) {
  return post("/api/v1/auth/forgot-password", { email });
}

/** POST /api/v1/auth/reset-password: sets a new password with the emailed code */
export function resetPassword(email, code, newPassword) {
  return post("/api/v1/auth/reset-password", { email, code, new_password: newPassword });
}

/** POST /api/v1/auth/change-password: for the logged-in user */
export function changePassword(currentPassword, newPassword) {
  return post("/api/v1/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}
