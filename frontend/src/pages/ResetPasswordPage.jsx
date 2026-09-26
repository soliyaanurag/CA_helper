import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router";
import { z } from "zod";

import { forgotPassword, resetPassword } from "@/api/auth";
import { errorMessage } from "@/api/client";
import { FormCard } from "@/components/FormCard";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import {
  codeSchema,
  emailSchema,
  newPasswordSchema,
  PASSWORD_RULE_TEXT,
  PASSWORDS_MATCH_ERROR,
  passwordsMatch,
} from "@/lib/authRules";

const resetSchema = z
  .object({
    email: emailSchema,
    code: codeSchema,
    password: newPasswordSchema,
    confirm_password: z.string(),
  })
  .refine(passwordsMatch, PASSWORDS_MATCH_ERROR);

/**
 * /reset-password: the emailed code plus a new password. The forgot-password
 * page passes the email in the location state.
 */
export function ResetPasswordPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [resending, setResending] = useState(false);
  const {
    register,
    handleSubmit,
    trigger,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(resetSchema),
    defaultValues: { email: location.state?.email ?? "" },
  });

  async function onSubmit({ email, code, password }) {
    setServerError(null);
    setNotice(null);
    try {
      await resetPassword(email, code, password);
      navigate("/login", {
        state: { email, notice: "Your password is reset. Log in with your new password." },
      });
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  async function onResend() {
    setServerError(null);
    setNotice(null);
    if (!(await trigger("email"))) return; // needs a valid email first
    setResending(true);
    try {
      await forgotPassword(getValues("email"));
      setNotice(
        "If this email has an account, we sent it a new code. We send at most one code a minute.",
      );
    } catch (error) {
      setServerError(errorMessage(error));
    } finally {
      setResending(false);
    }
  }

  return (
    <FormCard
      title="Reset your password"
      description="If an account uses this email, we sent it a 6-digit code. Enter it and choose a new password."
    >
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <FormField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email}
          {...register("email")}
        />
        <FormField
          id="code"
          label="Code"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          error={errors.code}
          {...register("code")}
        />
        <FormField
          id="password"
          label="New password"
          type="password"
          autoComplete="new-password"
          hint={PASSWORD_RULE_TEXT}
          error={errors.password}
          {...register("password")}
        />
        <FormField
          id="confirm_password"
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          error={errors.confirm_password}
          {...register("confirm_password")}
        />
        {serverError && (
          <p role="alert" className="text-sm text-destructive">
            {serverError}
          </p>
        )}
        {notice && (
          <p role="status" className="text-sm text-muted-foreground">
            {notice}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : "Reset password"}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="w-full"
          disabled={resending}
          onClick={onResend}
        >
          {resending ? "Sending..." : "Send a new code"}
        </Button>
      </form>
      <p className="text-sm text-muted-foreground">
        <Link to="/login" className="text-primary underline-offset-4 hover:underline">
          Back to log in
        </Link>
      </p>
    </FormCard>
  );
}
