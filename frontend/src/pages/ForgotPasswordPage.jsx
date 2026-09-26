import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router";
import { z } from "zod";

import { forgotPassword } from "@/api/auth";
import { errorMessage } from "@/api/client";
import { FormCard } from "@/components/FormCard";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import { emailSchema } from "@/lib/authRules";

const forgotSchema = z.object({ email: emailSchema });

/** /forgot-password: ask for a reset code by email, then continue on /reset-password. */
export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [serverError, setServerError] = useState(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(forgotSchema) });

  async function onSubmit({ email }) {
    setServerError(null);
    try {
      await forgotPassword(email);
      navigate("/reset-password", { state: { email } });
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <FormCard
      title="Forgot your password?"
      description="Enter your account's email and we will send you a 6-digit code to reset it."
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
        {serverError && (
          <p role="alert" className="text-sm text-destructive">
            {serverError}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Sending..." : "Send code"}
        </Button>
      </form>
      <p className="text-sm text-muted-foreground">
        Remembered it?{" "}
        <Link to="/login" className="text-primary underline-offset-4 hover:underline">
          Log in
        </Link>
      </p>
    </FormCard>
  );
}
