import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { z } from "zod";

import {
  ApiRequestError,
  changePassword,
  errorMessage,
  forgotPassword,
  resendVerificationCode,
  resetPassword,
  signup,
  useHealth,
  verifyEmail,
} from "@/api";
import { useAuth } from "@/auth";
import { FormCard, FormField } from "@/components/shared";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui";
import {
  codeSchema,
  emailSchema,
  label,
  newPasswordSchema,
  PASSWORD_RULE_TEXT,
  PASSWORDS_MATCH_ERROR,
  passwordsMatch,
  ROLE_HOME,
  USER_ROLE_LABELS,
} from "@/lib";

// --- HomePage ----------------------------------------------------------------------------------

// Each card links to where that audience starts: signup with the role chosen, or login.
const AUDIENCES = [
  {
    title: "Businesses",
    text: "Profile, compliance calendar, documents, find a CA.",
    action: "Create a business account",
    to: "/signup",
    state: { role: "business" },
  },
  {
    title: "Chartered Accountants",
    text: "Clients, deadlines and requests.",
    action: "Join as a CA",
    to: "/signup",
    state: { role: "ca" },
  },
  {
    title: "Admins",
    text: "Users, CA verification and configuration.",
    action: "Log in",
    to: "/login",
  },
];

/** The API status badge is for developers: shown in development, or when something is down. */
function showApiStatus(health) {
  if (import.meta.env.DEV || health.isError) return true;
  return health.isSuccess && health.data.status !== "ok";
}

/** Landing page: what the platform is, log in / sign up buttons, and (see above) API status. */
export function HomePage() {
  const health = useHealth();
  const { user } = useAuth();

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <h1 className="text-3xl font-semibold">CA Helper</h1>
        <p className="text-muted-foreground">
          Know which filings apply to your business and when. File yourself or work with a fairly
          priced CA.
        </p>
        {user ? (
          <Button asChild>
            <Link to={ROLE_HOME[user.role]}>Go to your dashboard</Link>
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button asChild>
              <Link to="/login">Log in</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/signup">Create an account</Link>
            </Button>
          </div>
        )}
        {showApiStatus(health) && (
          <p className="text-sm">
            API status:{" "}
            {health.isPending ? (
              <Badge variant="secondary">checking...</Badge>
            ) : health.isError ? (
              <Badge variant="destructive">unreachable</Badge>
            ) : health.data.status === "ok" ? (
              <Badge>ok</Badge>
            ) : (
              <Badge variant="destructive">API up, database {health.data.database}</Badge>
            )}
          </p>
        )}
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {AUDIENCES.map((audience) => (
          <Link
            key={audience.title}
            to={audience.to}
            state={audience.state}
            className="rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            <Card className="h-full transition-colors hover:bg-muted/50">
              <CardHeader>
                <CardTitle>{audience.title}</CardTitle>
                <CardDescription>{audience.text}</CardDescription>
                <span className="text-sm font-medium text-primary">{audience.action} →</span>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

// --- LoginPage ---------------------------------------------------------------------------------

const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Enter your password."),
});

/** What to tell the user for each login error code from the API. */
const LOGIN_ERROR_TEXT = {
  INVALID_CREDENTIALS: "Wrong email or password.",
  EMAIL_NOT_VERIFIED: "Your email is not verified yet.",
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

// --- SignupPage --------------------------------------------------------------------------------

/** The roles that may sign up (admins are created by the team). */
const SIGNUP_ROLES = ["business", "ca"];

const signupSchema = z
  .object({
    full_name: z.string().trim().min(1, "Enter your name.").max(200, "Use at most 200 characters."),
    email: emailSchema,
    role: z.enum(SIGNUP_ROLES, { error: "Choose how you will use CA Helper." }),
    password: newPasswordSchema,
    confirm_password: z.string(),
    terms_accepted: z.boolean(),
  })
  .refine(passwordsMatch, PASSWORDS_MATCH_ERROR)
  // A check on the whole form (not z.literal on the field), so it is shown together with
  // the other errors.
  .refine((form) => form.terms_accepted, {
    message: "Agree to the Terms and Privacy Policy to sign up.",
    path: ["terms_accepted"],
  });

/** /signup: create a business or CA account, then verify the email with the emailed code. */
export function SignupPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  // The landing page's "Join as a CA" card passes { role: "ca" }.
  const askedRole = useLocation().state?.role;
  const [serverError, setServerError] = useState(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      role: SIGNUP_ROLES.includes(askedRole) ? askedRole : "business",
      terms_accepted: false,
    },
  });

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
        <div className="space-y-1">
          <label htmlFor="terms_accepted" className="flex items-center gap-2 text-sm">
            <input id="terms_accepted" type="checkbox" {...register("terms_accepted")} />
            <span>
              I agree to the{" "}
              <Link
                to="/terms"
                target="_blank"
                className="text-primary underline-offset-4 hover:underline"
              >
                Terms and Privacy Policy
              </Link>
            </span>
          </label>
          {errors.terms_accepted && (
            <p className="text-sm text-destructive">{errors.terms_accepted.message}</p>
          )}
        </div>
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

// --- VerifyEmailPage ---------------------------------------------------------------------------

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
      setNotice("We sent a new code to this email.");
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

// --- ForgotPasswordPage ------------------------------------------------------------------------

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

// --- ResetPasswordPage -------------------------------------------------------------------------

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
      setNotice("We sent a new code to this email.");
    } catch (error) {
      setServerError(errorMessage(error));
    } finally {
      setResending(false);
    }
  }

  return (
    <FormCard
      title="Reset your password"
      description="We sent a 6-digit code to your email. Enter it and choose a new password."
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

// --- ChangePasswordPage ------------------------------------------------------------------------

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

// --- TermsPage ---------------------------------------------------------------------------------

// Plain-language terms: what we store, how it is protected, who sees it, what we do not do.
const SECTIONS = [
  {
    title: "What CA Helper does",
    points: [
      "It tells your business which tax filings apply and when they are due, helps you file them yourself, or connects you with a Chartered Accountant (CA).",
      "It never files a return for you and has no access to the government portals. Filing is done by you or by your CA.",
      "The profile and due dates are a guide. Check anything important with a CA.",
    ],
  },
  {
    title: "What we store",
    points: [
      "Your account: name, email and a hashed password (we never store the password itself).",
      "Your business details: name, type, state, address, turnover, PAN, GSTIN, TAN, phone and the answers you give on the profile form.",
      "Your filings and their status, and the documents you or your CA upload.",
    ],
  },
  {
    title: "How we protect it",
    points: [
      "PAN, GSTIN, TAN and phone numbers are encrypted in our database.",
      "Uploaded documents are encrypted and stored on our server; they are never sent anywhere else.",
      "Our AI assistant never receives your PAN, GSTIN, TAN, name, email, phone, address or documents.",
    ],
  },
  {
    title: "Who sees your data",
    points: [
      "A CA you send a request to sees only a summary (business type, state, size) and the filings in the request, not your PAN, GSTIN, TAN or documents.",
      "Once you and a CA agree, that CA sees your full profile, but only the filings in that engagement and the documents linked to them. When the work ends, their access ends.",
      "Our admins see account and verification details, never the contents of your documents.",
    ],
  },
];

/** /terms: the Terms and Privacy Policy, in plain language. */
export function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Terms and Privacy Policy</h1>
      {SECTIONS.map((section) => (
        <Card key={section.title}>
          <CardHeader>
            <CardTitle>{section.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-2 pl-5 text-sm">
              {section.points.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// --- NotFoundPage ------------------------------------------------------------------------------

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-md space-y-4 p-16 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <Link to="/" className="text-sm underline">
        Back to the home page
      </Link>
    </div>
  );
}
