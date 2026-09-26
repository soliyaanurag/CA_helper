import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router";
import { z } from "zod";

import { resendVerificationCode, verifyEmail } from "@/api/auth";
import { ApiRequestError, errorMessage } from "@/api/client";
import { FormCard } from "@/components/FormCard";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import { codeSchema, emailSchema } from "@/lib/authRules";

const verifySchema = z.object({ email: emailSchema, code: codeSchema });

/**
 * /verify-email: enter the 6-digit code emailed at signup, or ask for a new one.
 * The signup and login pages pass the email in the location state.
 */
export function VerifyEmailPage() {
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
    resolver: zodResolver(verifySchema),
    defaultValues: { email: location.state?.email ?? "", code: "" },
  });

  async function onSubmit({ email, code }) {
    setServerError(null);
    setNotice(null);
    try {
      await verifyEmail(email, code);
      navigate("/login", {
        state: { email, notice: "Your email is verified. You can log in now." },
      });
    } catch (error) {
      if (error instanceof ApiRequestError && error.code === "EMAIL_ALREADY_VERIFIED") {
        navigate("/login", { state: { email, notice: "Your email is already verified. Log in." } });
      } else {
        setServerError(errorMessage(error));
      }
    }
  }

  async function onResend() {
    setServerError(null);
    setNotice(null);
    if (!(await trigger("email"))) return; // needs a valid email first
    setResending(true);
    try {
      await resendVerificationCode(getValues("email"));
      setNotice(
        "If this email is waiting to be verified, we sent it a new code. We send at most one code a minute.",
      );
    } catch (error) {
      setServerError(errorMessage(error));
    } finally {
      setResending(false);
    }
  }

  return (
    <FormCard
      title="Verify your email"
      description="Enter the 6-digit code we emailed you. You can log in once your email is verified."
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
          {isSubmitting ? "Verifying..." : "Verify email"}
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
        Already verified?{" "}
        <Link to="/login" className="text-primary underline-offset-4 hover:underline">
          Log in
        </Link>
      </p>
    </FormCard>
  );
}
