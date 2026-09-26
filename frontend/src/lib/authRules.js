/**
 * Zod rules shared by the account forms (signup, verify email, reset and change
 * password). The backend checks the same rules in backend/app/schemas/auth.py.
 */
import { z } from "zod";

export const PASSWORD_RULE_TEXT =
  "Use 8 to 128 characters, with at least one letter and one number.";

/** A new password: 8 to 128 characters, at least one letter and one number. */
export const newPasswordSchema = z
  .string()
  .min(8, PASSWORD_RULE_TEXT)
  .max(128, PASSWORD_RULE_TEXT)
  .regex(/[A-Za-z]/, PASSWORD_RULE_TEXT)
  .regex(/[0-9]/, PASSWORD_RULE_TEXT);

/** The 6-digit code from an email (spaces around it are ignored). */
export const codeSchema = z
  .string()
  .trim()
  .regex(/^[0-9]{6}$/, "Enter the 6-digit code from the email.");

export const emailSchema = z.email("Enter a valid email address.");

/** Add to a form schema with `password` and `confirm_password` fields. */
export function passwordsMatch(values) {
  return values.password === values.confirm_password;
}

export const PASSWORDS_MATCH_ERROR = {
  message: "The passwords do not match.",
  path: ["confirm_password"],
};
