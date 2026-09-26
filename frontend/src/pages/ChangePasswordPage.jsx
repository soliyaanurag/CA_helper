import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { changePassword } from "@/api/auth";
import { errorMessage } from "@/api/client";
import { FormCard } from "@/components/FormCard";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import {
  newPasswordSchema,
  PASSWORD_RULE_TEXT,
  PASSWORDS_MATCH_ERROR,
  passwordsMatch,
} from "@/lib/authRules";

const changeSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password."),
    password: newPasswordSchema,
    confirm_password: z.string(),
  })
  .refine(passwordsMatch, PASSWORDS_MATCH_ERROR);

const EMPTY_FORM = { current_password: "", password: "", confirm_password: "" };

/**
 * <area>/change-password (every role, from the sidebar's "Change password" link).
 * A wrong current password is a 400 WRONG_PASSWORD, so it never logs the user out.
 */
export function ChangePasswordPage() {
  const [serverError, setServerError] = useState(null);
  const [done, setDone] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(changeSchema), defaultValues: EMPTY_FORM });

  async function onSubmit({ current_password, password }) {
    setServerError(null);
    setDone(false);
    try {
      await changePassword(current_password, password);
      reset(EMPTY_FORM);
      setDone(true);
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <FormCard title="Change password" description="We will email you when your password changes.">
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <FormField
          id="current_password"
          label="Current password"
          type="password"
          autoComplete="current-password"
          error={errors.current_password}
          {...register("current_password")}
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
        {done && (
          <p role="status" className="text-sm text-muted-foreground">
            Your password is changed.
          </p>
        )}
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : "Change password"}
        </Button>
      </form>
    </FormCard>
  );
}
