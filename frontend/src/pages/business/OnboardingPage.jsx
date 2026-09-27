import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import { errorMessage } from "@/api/client";
import { FILINGS_KEY } from "@/api/compliance";
import { MY_BUSINESS_KEY, registerBusiness, useMyBusiness } from "@/api/onboarding";
import { FormField } from "@/components/FormField";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  ENTITY_TYPE_LABELS,
  GST_SCHEME_LABELS,
  ITR_FORM_LABELS,
  MSME_TIER_LABELS,
  label,
} from "@/lib/labels";
import { formatRupees } from "@/lib/money";

/**
 * /business/onboarding: the business profile.
 * Not registered yet → the registration form. Registered → the regulatory profile,
 * with the reason ("why") under every line.
 */
export function OnboardingPage() {
  const myBusiness = useMyBusiness();

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Business profile</h1>
      {myBusiness.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {myBusiness.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(myBusiness.error)}
        </p>
      )}
      {myBusiness.isSuccess && myBusiness.data === null && <RegisterForm />}
      {myBusiness.isSuccess && myBusiness.data !== null && (
        <ProfileView business={myBusiness.data.business} profile={myBusiness.data.profile} />
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// The registration form
// ----------------------------------------------------------------------------

const AMOUNT = /^[0-9]+(\.[0-9]{1,2})?$/; // rupees, e.g. 4500000 or 4500000.50

// The same rules as BusinessInputSchema in backend/app/schemas/onboarding.py.
const registerSchema = z
  .object({
    legal_name: z.string().trim().min(1, "Enter the business name.").max(200),
    entity_type: z.string().min(1, "Choose the type of business."),
    state: z.string().trim().min(1, "Enter the state.").max(50),
    address: z.string().trim().min(1, "Enter the address.").max(500),
    description: z.string().trim().min(1, "Describe what the business does.").max(1000),
    annual_turnover: z.string().regex(AMOUNT, "Enter an amount in rupees, e.g. 4500000."),
    investment_amount: z.string().regex(AMOUNT, "Enter an amount in rupees, e.g. 800000."),
    pan: z
      .string()
      .trim()
      .toUpperCase()
      .regex(/^[A-Z]{5}[0-9]{4}[A-Z]$/, "Enter a valid PAN, e.g. ABCDE1234F."),
    phone: z.string().regex(/^[6-9][0-9]{9}$/, "Enter a 10-digit mobile number."),
    gst_registered: z.boolean(),
    gstin: z.string().trim().toUpperCase(),
    gst_composition: z.boolean(),
    deducts_tds: z.boolean(),
    tan: z.string().trim().toUpperCase(),
    pays_salary_above_limit: z.boolean(),
    cin_llpin: z.string().trim().toUpperCase(),
    udyam_number: z.string().trim().toUpperCase(),
  })
  // Fields that are needed only for some businesses.
  .superRefine((form, ctx) => {
    if (
      form.gst_registered &&
      !/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$/.test(form.gstin)
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["gstin"],
        message: "Enter a valid 15-character GSTIN.",
      });
    }
    if (form.deducts_tds && !/^[A-Z]{4}[0-9]{5}[A-Z]$/.test(form.tan)) {
      ctx.addIssue({
        code: "custom",
        path: ["tan"],
        message: "Enter a valid TAN, e.g. MUMA12345B.",
      });
    }
    if (["llp", "private_limited"].includes(form.entity_type) && !form.cin_llpin) {
      ctx.addIssue({ code: "custom", path: ["cin_llpin"], message: "Enter the CIN or LLPIN." });
    }
    if (form.udyam_number && !/^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$/.test(form.udyam_number)) {
      ctx.addIssue({
        code: "custom",
        path: ["udyam_number"],
        message: "Enter it like UDYAM-MH-01-0000001, or leave it empty.",
      });
    }
  });

const EMPTY_FORM = {
  legal_name: "",
  entity_type: "",
  state: "",
  address: "",
  description: "",
  annual_turnover: "",
  investment_amount: "",
  pan: "",
  phone: "",
  gst_registered: false,
  gstin: "",
  gst_composition: false,
  deducts_tds: false,
  tan: "",
  pays_salary_above_limit: false,
  cin_llpin: "",
  udyam_number: "",
};

const SELECT_CLASS =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

function RegisterForm() {
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState(null);
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(registerSchema), defaultValues: EMPTY_FORM });

  // Some fields appear only after a tick or a choice.
  const gstRegistered = useWatch({ control, name: "gst_registered" });
  const deductsTds = useWatch({ control, name: "deducts_tds" });
  const entityType = useWatch({ control, name: "entity_type" });
  const needsCin = entityType === "llp" || entityType === "private_limited";

  async function onSubmit(values) {
    setServerError(null);
    // Send empty codes as null, and only the ones that apply.
    const form = {
      ...values,
      gstin: values.gst_registered ? values.gstin : null,
      gst_composition: values.gst_registered && values.gst_composition,
      tan: values.deducts_tds ? values.tan : null,
      pays_salary_above_limit: values.deducts_tds && values.pays_salary_above_limit,
      cin_llpin: needsCin ? values.cin_llpin : null,
      udyam_number: values.udyam_number || null,
    };
    try {
      const saved = await registerBusiness(form);
      queryClient.setQueryData(MY_BUSINESS_KEY, saved); // shows the profile at once
      queryClient.invalidateQueries({ queryKey: FILINGS_KEY }); // new filings were created
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Register your business</CardTitle>
        <CardDescription>
          We use these details to work out which filings apply to you and when they are due. PAN,
          GSTIN, TAN and phone are stored encrypted.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="legal_name"
              label="Business name"
              error={errors.legal_name}
              {...register("legal_name")}
            />
            <div className="space-y-2">
              <Label htmlFor="entity_type">Type of business</Label>
              <select id="entity_type" className={SELECT_CLASS} {...register("entity_type")}>
                <option value="">Choose...</option>
                {Object.entries(ENTITY_TYPE_LABELS).map(([code, text]) => (
                  <option key={code} value={code}>
                    {text}
                  </option>
                ))}
              </select>
              {errors.entity_type && (
                <p className="text-sm text-destructive">{errors.entity_type.message}</p>
              )}
            </div>
            <FormField id="state" label="State" error={errors.state} {...register("state")} />
            <FormField
              id="phone"
              label="Mobile number"
              inputMode="numeric"
              error={errors.phone}
              {...register("phone")}
            />
            <FormField
              id="annual_turnover"
              label="Annual turnover (₹)"
              inputMode="decimal"
              error={errors.annual_turnover}
              {...register("annual_turnover")}
            />
            <FormField
              id="investment_amount"
              label="Investment in plant & machinery (₹)"
              inputMode="decimal"
              error={errors.investment_amount}
              {...register("investment_amount")}
            />
            <FormField id="pan" label="PAN" error={errors.pan} {...register("pan")} />
            <FormField
              id="udyam_number"
              label="Udyam number (optional)"
              error={errors.udyam_number}
              {...register("udyam_number")}
            />
            {needsCin && (
              <FormField
                id="cin_llpin"
                label="CIN (company) or LLPIN (LLP)"
                error={errors.cin_llpin}
                {...register("cin_llpin")}
              />
            )}
          </div>
          <FormField id="address" label="Address" error={errors.address} {...register("address")} />
          <FormField
            id="description"
            label="What does the business do?"
            error={errors.description}
            {...register("description")}
          />

          <fieldset className="space-y-3">
            <legend className="text-sm font-medium">GST</legend>
            <Checkbox id="gst_registered" text="GST registered" {...register("gst_registered")} />
            {gstRegistered && (
              <>
                <FormField id="gstin" label="GSTIN" error={errors.gstin} {...register("gstin")} />
                <Checkbox
                  id="gst_composition"
                  text="I chose the composition scheme"
                  {...register("gst_composition")}
                />
              </>
            )}
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-sm font-medium">TDS</legend>
            <Checkbox id="deducts_tds" text="I deduct TDS" {...register("deducts_tds")} />
            {deductsTds && (
              <>
                <FormField id="tan" label="TAN" error={errors.tan} {...register("tan")} />
                <Checkbox
                  id="pays_salary_above_limit"
                  text="I pay salaries above the taxable limit"
                  {...register("pays_salary_above_limit")}
                />
              </>
            )}
          </fieldset>

          {serverError && (
            <p role="alert" className="text-sm text-destructive">
              {serverError}
            </p>
          )}
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving..." : "Register business"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function Checkbox({ id, text, ...inputProps }) {
  return (
    <label htmlFor={id} className="flex items-center gap-2 text-sm">
      <input id={id} type="checkbox" {...inputProps} />
      {text}
    </label>
  );
}

// ----------------------------------------------------------------------------
// The regulatory profile
// ----------------------------------------------------------------------------

function yesNo(value) {
  return value ? "Yes" : "No";
}

function ProfileView({ business, profile }) {
  // One row per profile line: [title, value, key of its "why" in profile.explanations].
  const rows = [
    ["MSME tier", label(MSME_TIER_LABELS, profile.msme_tier), "msme_tier"],
    ["GST scheme", label(GST_SCHEME_LABELS, profile.gst_scheme), "gst_scheme"],
    ["Income tax return form", label(ITR_FORM_LABELS, profile.itr_form), "itr_form"],
    ["Presumptive scheme", yesNo(profile.presumptive_eligible), "presumptive_eligible"],
    ["Tax audit", yesNo(profile.audit_applicable), "audit_applicable"],
    ["TDS return 24Q (salaries)", yesNo(profile.files_24q), "files_24q"],
    ["TDS return 26Q (other payments)", yesNo(profile.files_26q), "files_26q"],
  ];

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{business.legal_name}</CardTitle>
          <CardDescription>
            {label(ENTITY_TYPE_LABELS, business.entity_type)} · {business.state} · turnover{" "}
            {formatRupees(business.annual_turnover)}
          </CardDescription>
        </CardHeader>
      </Card>

      {profile.gst_registration_suggested && (
        <p role="alert" className="rounded-lg bg-amber-100 p-3 text-sm text-amber-900">
          {profile.explanations.gst_scheme}
        </p>
      )}
      {profile.roc_not_tracked && (
        <p className="rounded-lg bg-muted p-3 text-sm">{profile.explanations.roc_not_tracked}</p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Your regulatory profile</CardTitle>
          <CardDescription>What applies to your business, and why.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="divide-y">
            {rows.map(([title, value, key]) => (
              <div key={key} className="grid gap-1 py-3 sm:grid-cols-3">
                <dt className="text-sm font-medium">{title}</dt>
                <dd className="sm:col-span-2">
                  <p className="text-sm font-semibold">{value}</p>
                  <p className="text-sm text-muted-foreground">{profile.explanations[key]}</p>
                </dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      <p className="text-sm">
        Your filings are in the{" "}
        <Link to="/business/compliance" className="underline">
          compliance calendar
        </Link>
        .
      </p>
      <p className="text-xs text-muted-foreground">
        The legal limits behind this profile are still being verified. Check with a CA before
        relying on it.
      </p>
    </>
  );
}
