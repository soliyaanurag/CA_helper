import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useNavigate } from "react-router";
import { z } from "zod";

import { signup } from "@/api/auth";
import { errorMessage } from "@/api/client";
import { FormCard } from "@/components/FormCard";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import {
  emailSchema,
  newPasswordSchema,
  PASSWORD_RULE_TEXT,
  PASSWORDS_MATCH_ERROR,
  passwordsMatch,
} from "@/lib/authRules";
import { label, USER_ROLE_LABELS } from "@/lib/labels";
import { ROLE_HOME } from "@/lib/session";

/** The roles that may sign up (admins are created by the team). */
const SIGNUP_ROLES = ["business", "ca"];

const signupSchema = z
  .object({
    full_name: z.string().trim().min(1, "Enter your name.").max(200, "Use at most 200 characters."),
    email: emailSchema,
    role: z.enum(SIGNUP_ROLES, { error: "Choose how you will use CA Helper." }),
    password: newPasswordSchema,
    confirm_password: z.string(),
  })
  .refine(passwordsMatch, PASSWORDS_MATCH_ERROR);

/** /signup: create a business or CA account, then verify the email with the emailed code. */
export function SignupPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(signupSchema), defaultValues: { role: "business" } });

  if (user) return <Navigate to={ROLE_HOME[user.role]} replace />;

  async function onSubmit(values) {
    setServerError(null);
    try {
      await signup(values);
      navigate("/verify-email", { state: { email: values.email } });
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <FormCard
      title="Create an account"
      description="For businesses, freelancers and Chartered Accountants."
    >
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <FormField
          id="full_name"
          label="Full name"
          autoComplete="name"
          error={errors.full_name}
          {...register("full_name")}
        />
        <FormField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email}
          {...register("email")}
        />
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">I am signing up as</legend>
          {SIGNUP_ROLES.map((role) => (
            <label key={role} className="flex items-center gap-2 text-sm">
              <input type="radio" value={role} {...register("role")} />
              {label(USER_ROLE_LABELS, role)}
            </label>
          ))}
          {errors.role && <p className="text-sm text-destructive">{errors.role.message}</p>}
        </fieldset>
        <FormField
          id="password"
          label="Password"
          type="password"
          autoComplete="new-password"
          hint={PASSWORD_RULE_TEXT}
          error={errors.password}
          {...register("password")}
        />
        <FormField
          id="confirm_password"
          label="Confirm password"
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
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Creating account..." : "Create account"}
        </Button>
      </form>
      <p className="text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link to="/login" className="text-primary underline-offset-4 hover:underline">
          Log in
        </Link>
      </p>
    </FormCard>
  );
}
