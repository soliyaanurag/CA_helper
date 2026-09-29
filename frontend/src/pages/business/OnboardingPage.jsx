import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import { errorMessage } from "@/api/client";
import { FILINGS_KEY } from "@/api/compliance";
import {
  MY_BUSINESS_KEY,
  readRegistrationDocument,
  registerBusiness,
  updateBusiness,
  useGstStates,
  useMyBusiness,
} from "@/api/onboarding";
import { FormField } from "@/components/FormField";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { gstinError } from "@/lib/gstin";
import { NicCodeCard } from "@/pages/business/NicCodeCard";
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
 * Not registered yet → the registration form. Registered → the regulatory profile (a row
 * of chips, then every line with its reason), and "Edit details", which opens the same
 * form filled in; after saving, "What changed" lists the profile lines and filings that
 * changed.
 */
export function OnboardingPage() {
  const myBusiness = useMyBusiness();
  const states = useGstStates();
  const [editing, setEditing] = useState(false);
  const [changes, setChanges] = useState(null);

  let content;
  if (myBusiness.isPending || states.isPending) {
    content = <p className="text-sm text-muted-foreground">Loading...</p>;
  } else if (myBusiness.isError || states.isError) {
    content = (
      <p role="alert" className="text-sm text-destructive">
        {errorMessage(myBusiness.error || states.error)}
      </p>
    );
  } else if (myBusiness.data === null) {
    content = <BusinessForm states={states.data} />;
  } else if (editing) {
    content = (
      <BusinessForm
        states={states.data}
        business={myBusiness.data.business}
        onSaved={(saved) => {
          setChanges(saved.changes);
          setEditing(false);
        }}
        onCancel={() => setEditing(false)}
      />
    );
  } else {
    content = (
      <>
        {changes && <WhatChanged changes={changes} />}
        <ProfileView
          business={myBusiness.data.business}
          profile={myBusiness.data.profile}
          nicCode={myBusiness.data.nic_code}
          onEdit={() => {
            setChanges(null);
            setEditing(true);
          }}
        />
      </>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Business profile</h1>
      {content}
    </div>
  );
}

// ----------------------------------------------------------------------------
// The registration / edit form
// ----------------------------------------------------------------------------

const AMOUNT = /^[0-9]+(\.[0-9]{1,2})?$/; // rupees, e.g. 4500000 or 4500000.50
const GSTIN_FORMAT = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$/;

// The same rules as BusinessInputSchema in backend/app/schemas/onboarding.py.
// `states` is [{name, code}]: the state must be one of them, and a GSTIN must fit it.
function makeSchema(states) {
  const codeOf = Object.fromEntries(states.map((state) => [state.name, state.code]));
  return (
    z
      .object({
        legal_name: z.string().trim().min(1, "Enter the business name.").max(200),
        entity_type: z.string().min(1, "Choose the type of business."),
        state: z.string().refine((name) => name in codeOf, "Choose your state from the list."),
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
        gst_returns: z.enum(["monthly", "quarterly"]),
        accounts_audited_other_law: z.boolean(),
        deducts_tds: z.boolean(),
        tan: z.string().trim().toUpperCase(),
        pays_salary_above_limit: z.boolean(),
        cin_llpin: z.string().trim().toUpperCase(),
        udyam_number: z.string().trim().toUpperCase(),
      })
      // Fields that are needed only for some businesses.
      .superRefine((form, ctx) => {
        if (form.gst_registered) {
          const problem = GSTIN_FORMAT.test(form.gstin)
            ? gstinError(form.gstin, form.pan, form.state, codeOf[form.state])
            : "Enter a valid 15-character GSTIN.";
          if (problem) {
            ctx.addIssue({ code: "custom", path: ["gstin"], message: problem });
          }
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
      })
  );
}

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
  gst_returns: "monthly",
  accounts_audited_other_law: false,
  deducts_tds: false,
  tan: "",
  pays_salary_above_limit: false,
  cin_llpin: "",
  udyam_number: "",
};

// The saved business as form values: only the form's own fields (the API refuses
// others), amounts as typed, empty codes as "".
function formValues(business) {
  const values = {};
  for (const key of Object.keys(EMPTY_FORM)) {
    values[key] = business[key] ?? EMPTY_FORM[key];
  }
  values.state = business.state_needs_review ? "" : business.state;
  values.annual_turnover = String(Number(business.annual_turnover));
  values.investment_amount = String(Number(business.investment_amount));
  values.gst_returns = business.gst_qrmp ? "quarterly" : "monthly";
  return values;
}

const SELECT_CLASS =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

/** Registers a business (no `business`) or edits the saved one. */
function BusinessForm({ states, business, onSaved, onCancel }) {
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState(null);
  const schema = useMemo(() => makeSchema(states), [states]);
  const {
    register,
    handleSubmit,
    control,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: business ? formValues(business) : EMPTY_FORM,
  });

  // Some fields appear only after a tick or a choice.
  const gstRegistered = useWatch({ control, name: "gst_registered" });
  const composition = useWatch({ control, name: "gst_composition" });
  const deductsTds = useWatch({ control, name: "deducts_tds" });
  const entityType = useWatch({ control, name: "entity_type" });
  const needsCin = entityType === "llp" || entityType === "private_limited";
  const asksOtherAudit = entityType === "partnership" || entityType === "llp";

  async function onSubmit(values) {
    setServerError(null);
    const { gst_returns, ...rest } = values;
    // Send empty codes as null, and only the ones that apply.
    const form = {
      ...rest,
      gstin: values.gst_registered ? values.gstin : null,
      gst_composition: values.gst_registered && values.gst_composition,
      gst_qrmp: values.gst_registered && !values.gst_composition && gst_returns === "quarterly",
      accounts_audited_other_law: asksOtherAudit && values.accounts_audited_other_law,
      tan: values.deducts_tds ? values.tan : null,
      pays_salary_above_limit: values.deducts_tds && values.pays_salary_above_limit,
      cin_llpin: needsCin ? values.cin_llpin : null,
      udyam_number: values.udyam_number || null,
    };
    try {
      const saved = business ? await updateBusiness(form) : await registerBusiness(form);
      queryClient.setQueryData(MY_BUSINESS_KEY, {
        business: saved.business,
        profile: saved.profile,
        nic_code: saved.nic_code,
      });
      queryClient.invalidateQueries({ queryKey: FILINGS_KEY }); // the filings may have changed
      onSaved?.(saved);
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{business ? "Edit your business details" : "Register your business"}</CardTitle>
        <CardDescription>
          We use these details to work out which filings apply to you and when they are due. PAN,
          GSTIN, TAN and phone are stored encrypted.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!business && <FillFromDocument setValue={setValue} />}
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
            <div className="space-y-2">
              <Label htmlFor="state">State</Label>
              <select id="state" className={SELECT_CLASS} {...register("state")}>
                <option value="">Choose...</option>
                {states.map((state) => (
                  <option key={state.code} value={state.name}>
                    {state.name}
                  </option>
                ))}
              </select>
              {errors.state && <p className="text-sm text-destructive">{errors.state.message}</p>}
              {business?.state_needs_review && !errors.state && (
                <p className="text-xs text-muted-foreground">
                  You typed "{business.state}" before this list existed: please choose it again.
                </p>
              )}
            </div>
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
            hint="In your own words, e.g. 'We bake biscuits and cakes'. It is used to suggest your activity code, so leave out names, phone numbers and emails."
            error={errors.description}
            {...register("description")}
          />

          {asksOtherAudit && (
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Audit</legend>
              <Checkbox
                id="accounts_audited_other_law"
                text="Our accounts are audited under another law (for example the LLP Act or our partnership deed)"
                {...register("accounts_audited_other_law")}
              />
              <p className="text-xs text-muted-foreground">
                LLPs above certain limits, and firms whose deed requires it, have their accounts
                audited every year. Ask your CA if you are not sure. An audit moves the income tax
                return's due date.
              </p>
            </fieldset>
          )}

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
                {!composition && (
                  <div className="space-y-1">
                    <p className="text-sm">How do you file GST returns?</p>
                    <div className="flex gap-4">
                      <Radio
                        id="gst_monthly"
                        value="monthly"
                        text="Monthly"
                        {...register("gst_returns")}
                      />
                      <Radio
                        id="gst_quarterly"
                        value="quarterly"
                        text="Quarterly (QRMP)"
                        {...register("gst_returns")}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Quarterly returns (QRMP) are allowed up to a turnover limit; above it, returns
                      are monthly and your profile will say so.
                    </p>
                  </div>
                )}
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
          <div className="flex gap-2">
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : business ? "Save changes" : "Register business"}
            </Button>
            {onCancel && (
              <Button type="button" variant="outline" onClick={onCancel}>
                Cancel
              </Button>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

// The form fields ON13 can fill, with the names people see.
const FILLABLE = {
  legal_name: "business name",
  entity_type: "type of business",
  state: "state",
  pan: "PAN",
  gstin: "GSTIN",
};

/**
 * ON13: "Fill in from a document". The server reads a GST certificate or PAN card with
 * OCR (locally; the file is not stored) and the found values go into the form. The user
 * checks them before registering.
 */
function FillFromDocument({ setValue }) {
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function onFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    setMessage(null);
    setError(null);
    setBusy(true);
    try {
      const { found } = await readRegistrationDocument(file);
      const filled = [];
      for (const [field, name] of Object.entries(FILLABLE)) {
        if (found[field]) {
          setValue(field, found[field], { shouldValidate: true });
          filled.push(name);
        }
      }
      if (found.gstin) setValue("gst_registered", true);
      setMessage(
        filled.length
          ? `Filled in: ${filled.join(", ")}. Check them before you register.`
          : "We could not find any details in this file. Please type them in.",
      );
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
      event.target.value = ""; // the same file can be chosen again
    }
  }

  return (
    <div className="mb-6 space-y-2 rounded-lg border border-dashed p-4">
      <Label htmlFor="autofill_file">
        Fill in from your GST certificate or PAN card (optional)
      </Label>
      <input
        id="autofill_file"
        type="file"
        accept="application/pdf,image/jpeg,image/png"
        className="block text-sm"
        disabled={busy}
        onChange={onFile}
      />
      <p className="text-xs text-muted-foreground">
        {busy
          ? "Reading the file..."
          : "The file is read on our server and not kept. Nothing is saved until you register."}
      </p>
      {message && (
        <p role="status" className="text-sm">
          {message}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
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

function Radio({ id, text, ...inputProps }) {
  return (
    <label htmlFor={id} className="flex items-center gap-2 text-sm">
      <input id={id} type="radio" {...inputProps} />
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

// Every profile line: [code in the profile, title, how to show its value].
const LINES = [
  ["msme_tier", "MSME tier", (value) => label(MSME_TIER_LABELS, value)],
  ["gst_scheme", "GST scheme", (value) => label(GST_SCHEME_LABELS, value)],
  ["itr_form", "Income tax return form", (value) => label(ITR_FORM_LABELS, value)],
  ["presumptive_eligible", "Presumptive scheme", yesNo],
  ["audit_applicable", "Tax audit (s.44AB)", yesNo],
  ["other_audit_applicable", "Accounts audited under another law", yesNo],
  ["files_24q", "TDS return 24Q (salaries)", yesNo],
  ["files_26q", "TDS return 26Q (other payments)", yesNo],
];

// The short summary at the top of the profile, e.g. Micro · QRMP · ITR-4 · 26Q.
function summaryChips(profile) {
  const chips = [label(MSME_TIER_LABELS, profile.msme_tier)];
  if (profile.gst_scheme === "regular_qrmp") chips.push("QRMP");
  else if (profile.gst_scheme === "regular_monthly") chips.push("GST monthly");
  else if (profile.gst_scheme === "composition") chips.push("Composition");
  else chips.push("No GST");
  chips.push(label(ITR_FORM_LABELS, profile.itr_form));
  if (profile.presumptive_eligible) chips.push("Presumptive");
  if (profile.audit_applicable || profile.other_audit_applicable) chips.push("Audit");
  if (profile.files_24q) chips.push("24Q");
  if (profile.files_26q) chips.push("26Q");
  return chips;
}

function ProfileView({ business, profile, nicCode, onEdit }) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{business.legal_name}</CardTitle>
          <CardDescription>
            {label(ENTITY_TYPE_LABELS, business.entity_type)} · {business.state} · turnover{" "}
            {formatRupees(business.annual_turnover)}
          </CardDescription>
          <ul className="flex flex-wrap gap-2 pt-1" aria-label="Profile summary">
            {summaryChips(profile).map((chip) => (
              <li key={chip}>
                <Badge variant="secondary">{chip}</Badge>
              </li>
            ))}
          </ul>
          <div className="pt-2">
            <Button variant="outline" size="sm" onClick={onEdit}>
              Edit details
            </Button>
          </div>
        </CardHeader>
      </Card>

      {business.state_needs_review && (
        <p role="alert" className="rounded-lg bg-amber-100 p-3 text-sm text-amber-900">
          Your state "{business.state}" is not in our list. Choose it again with Edit details.
        </p>
      )}
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
          <CardDescription>What applies to your business. Open a line to see why.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="divide-y">
            {LINES.map(([key, title, show]) => (
              <details key={key} className="py-3">
                <summary className="flex cursor-pointer justify-between gap-4 text-sm">
                  <span className="font-medium">{title}</span>
                  <span className="font-semibold">{show(profile[key])}</span>
                </summary>
                <p className="pt-1 text-sm text-muted-foreground">{profile.explanations[key]}</p>
              </details>
            ))}
          </div>
        </CardContent>
      </Card>

      <NicCodeCard nicCode={nicCode} />

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

// ----------------------------------------------------------------------------
// After an edit: what changed
// ----------------------------------------------------------------------------

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function WhatChanged({ changes }) {
  const filings = changes.filings;
  const filingLines = [];
  if (filings.added) filingLines.push(`${plural(filings.added, "filing")} added`);
  if (filings.restored) filingLines.push(`${plural(filings.restored, "filing")} back again`);
  if (filings.removed) filingLines.push(`${plural(filings.removed, "filing")} no longer needed`);
  if (filings.moved)
    filingLines.push(`${plural(filings.moved, "filing")} with a new period or due date`);
  if (filings.kept_with_ca) {
    filingLines.push(
      `${plural(filings.kept_with_ca, "filing")} kept although no longer needed, because a CA has it`,
    );
  }

  return (
    <Card role="status">
      <CardHeader>
        <CardTitle>Saved. What changed</CardTitle>
        {changes.profile.length === 0 && filingLines.length === 0 && (
          <CardDescription>Nothing in your profile or filings changed.</CardDescription>
        )}
      </CardHeader>
      {(changes.profile.length > 0 || filingLines.length > 0) && (
        <CardContent>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {changes.profile.map((change) => {
              const [, title, show] = LINES.find(([key]) => key === change.line);
              return (
                <li key={change.line}>
                  {title}: {show(change.old)} → {show(change.new)}
                </li>
              );
            })}
            {filingLines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </CardContent>
      )}
    </Card>
  );
}
