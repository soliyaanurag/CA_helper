import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation } from "react-router";
import { z } from "zod";

import { LoginError, useAuth } from "@/core/auth/auth-context";
import { ROLE_HOME, type Role } from "@/core/auth/session";
import { Button } from "@/core/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/core/components/ui/card";
import { Input } from "@/core/components/ui/input";
import { Label } from "@/core/components/ui/label";

const loginSchema = z.object({
  email: z.email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});
type LoginForm = z.infer<typeof loginSchema>;

/** What to tell the user for each login error code from the API. */
const LOGIN_ERROR_TEXT: Record<string, string> = {
  INVALID_CREDENTIALS: "Wrong email or password.",
  ACCOUNT_INACTIVE: "This account is inactive. Please contact support.",
  TOO_MANY_REQUESTS: "Too many login attempts. Wait a minute and try again.",
};

function errorText(error: unknown): string {
  if (error instanceof LoginError) {
    const known = LOGIN_ERROR_TEXT[error.code];
    if (known) return known;
    const ref = error.requestId ? ` (reference: ${error.requestId})` : "";
    return `Login failed: ${error.message}${ref}`;
  }
  return "Cannot reach the server. Check your connection and try again.";
}

/** After login: back to the page the guard sent the user from, if it is in their area. */
function destination(role: Role, from: string | undefined): string {
  const home = ROLE_HOME[role];
  return from && (from === home || from.startsWith(`${home}/`)) ? from : home;
}

export function LoginPage() {
  const { user, login } = useAuth();
  const from = (useLocation().state as { from?: string } | null)?.from;
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  // Logged in (already, or just now by onSubmit): go to the right page.
  if (user) return <Navigate to={destination(user.role, from)} replace />;

  async function onSubmit(values: LoginForm) {
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
