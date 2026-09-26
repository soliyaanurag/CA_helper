import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation } from "react-router";
import { z } from "zod";

import { ApiRequestError, errorMessage } from "@/api/client";
import { useAuth } from "@/hooks/useAuth";
import { ROLE_HOME } from "@/lib/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const loginSchema = z.object({
  email: z.email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

/** What to tell the user for each login error code from the API. */
const LOGIN_ERROR_TEXT = {
  INVALID_CREDENTIALS: "Wrong email or password.",
  ACCOUNT_INACTIVE: "This account is inactive. Please contact support.",
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

export function LoginPage() {
  const { user, login } = useAuth();
  const from = useLocation().state?.from;
  const [serverError, setServerError] = useState(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(loginSchema) });

  // Logged in (already, or just now by onSubmit): go to the right page.
  if (user) return <Navigate to={destination(user.role, from)} replace />;

  async function onSubmit(values) {
    setServerError(null);
    try {
      await login(values.email, values.password);
    } catch (error) {
      setServerError(errorText(error));
    }
  }

  return (
    <Card className="mx-auto max-w-sm">
      <CardHeader>
        <CardTitle>
          <h1 className="text-xl font-semibold">Log in</h1>
        </CardTitle>
        <CardDescription>Businesses, CAs and admins all log in here.</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              aria-invalid={!!errors.email}
              {...register("email")}
            />
            {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              aria-invalid={!!errors.password}
              {...register("password")}
            />
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>
          {serverError && (
            <p role="alert" className="text-sm text-destructive">
              {serverError}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Logging in..." : "Log in"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
