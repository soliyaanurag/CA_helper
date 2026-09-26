import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation } from "react-router";
import { z } from "zod";

import { ApiRequestError, errorMessage } from "@/api/client";
import { FormCard } from "@/components/FormCard";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { emailSchema } from "@/lib/authRules";
import { ROLE_HOME } from "@/lib/session";

const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Enter your password."),
});

/** What to tell the user for each login error code from the API. */
const LOGIN_ERROR_TEXT = {
  INVALID_CREDENTIALS: "Wrong email or password.",
  ACCOUNT_INACTIVE: "This account is inactive. Please contact support.",
  EMAIL_NOT_VERIFIED: "Your email is not verified yet.",
  TOO_MANY_REQUESTS: "Too many login attempts. Wait a minute and try again.",
};

function errorText(error) {
  if (error instanceof ApiRequestError && LOGIN_ERROR_TEXT[error.code]) {
    return LOGIN_ERROR_TEXT[error.code];
  }
  return errorMessage(error);
}

/** After login: back to the page the guard sent the user from, if it is in their area. */
function destination(role, from) {
  const home = ROLE_HOME[role];
  return from && (from === home || from.startsWith(`${home}/`)) ? from : home;
}

const LINK = "text-primary underline-offset-4 hover:underline";

/**
 * /login. The location state may carry `from` (set by the route guard), and
 * `email` + `notice` (set after verifying an email or resetting a password).
 */
export function LoginPage() {
  const { user, login } = useAuth();
  const { from, email, notice } = useLocation().state ?? {};
  const [serverError, setServerError] = useState(null);
  // Set when the API says EMAIL_NOT_VERIFIED: the error then links to /verify-email.
  const [unverifiedEmail, setUnverifiedEmail] = useState(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(loginSchema), defaultValues: { email: email ?? "" } });

  // Logged in (already, or just now by onSubmit): go to the right page.
  if (user) return <Navigate to={destination(user.role, from)} replace />;

  async function onSubmit(values) {
    setServerError(null);
    setUnverifiedEmail(null);
    try {
      await login(values.email, values.password);
    } catch (error) {
      setServerError(errorText(error));
      if (error instanceof ApiRequestError && error.code === "EMAIL_NOT_VERIFIED") {
        setUnverifiedEmail(values.email);
      }
    }
  }

  return (
    <FormCard title="Log in" description="Businesses, CAs and admins all log in here.">
      {notice && (
        <p role="status" className="text-sm text-muted-foreground">
          {notice}
        </p>
      )}
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
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password}
          {...register("password")}
        />
        {serverError && (
          <p role="alert" className="text-sm text-destructive">
            {serverError}{" "}
            {unverifiedEmail && (
              <Link to="/verify-email" state={{ email: unverifiedEmail }} className={LINK}>
                Enter your code
              </Link>
            )}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Logging in..." : "Log in"}
        </Button>
      </form>
      <div className="flex justify-between text-sm">
        <Link to="/forgot-password" className={LINK}>
          Forgot password?
        </Link>
        <Link to="/signup" className={LINK}>
          Create an account
        </Link>
      </div>
    </FormCard>
  );
}
