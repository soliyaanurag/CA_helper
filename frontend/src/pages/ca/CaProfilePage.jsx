import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { errorMessage } from "@/api/client";
import { CA_PROFILE_KEY, saveCaProfile, useCaProfile } from "@/api/marketplace";
import { FormField } from "@/components/FormField";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  CA_LANGUAGE_LABELS,
  CA_SPECIALIZATION_LABELS,
  CA_VERIFICATION_STATUS_LABELS,
  label,
} from "@/lib/labels";

// The same rules as CaProfileInputSchema in backend/app/schemas/marketplace.py.
const profileSchema = z.object({
  membership_no: z.string().regex(/^[0-9]{6}$/, "Enter your 6-digit ICAI membership number."),
  cop_number: z.string().trim().min(1, "Enter your Certificate of Practice number.").max(20),
  city: z.string().trim().min(1, "Enter your city.").max(100),
  languages: z.array(z.string()).min(1, "Choose at least one language."),
  specializations: z.array(z.string()).min(1, "Choose at least one specialization."),
  capacity: z.coerce.number().int().min(1, "Enter a number from 1 to 1000.").max(1000),
  years_experience: z.coerce.number().int().min(0, "Enter a number from 0 to 70.").max(70),
  about: z.string().trim().max(500, "Use at most 500 characters."),
});

const EMPTY_FORM = {
  membership_no: "",
  cop_number: "",
  city: "",
  languages: [],
  specializations: [],
  capacity: "",
  years_experience: "",
  about: "",
};

// Badge colour for each verification status: red until verified, then green.
const STATUS_COLORS = {
  pending: "bg-red-100 text-red-700",
  verified: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

/** What each verification status means for the CA. */
const STATUS_TEXT = {
  pending:
    "An admin is checking your membership and CoP numbers. You will appear in the marketplace once verified.",
  verified:
    "Businesses can find you in the marketplace. Changing your membership or CoP number needs a new check.",
  rejected:
    "An admin could not confirm your numbers. Correct your details and save to ask for a new check.",
};

/**
 * /ca/profile: the CA's practice profile. Saving it (first time, or with a new
 * membership/CoP number) sends it to an admin for verification; only verified CAs
 * are listed for businesses.
 */
export function CaProfilePage() {
  const profile = useCaProfile();

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">My profile</h1>
      {profile.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {profile.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(profile.error)}
        </p>
      )}
      {profile.isSuccess && (
        <>
          <StatusCard profile={profile.data} />
          <CaProfileForm profile={profile.data} />
        </>
      )}
    </div>
  );
}

function StatusCard({ profile }) {
  const status = profile?.verification_status;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Verification
          {status && (
            <Badge className={STATUS_COLORS[status]}>
              {label(CA_VERIFICATION_STATUS_LABELS, status)}
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          {status
            ? STATUS_TEXT[status]
            : "Complete your profile. An admin checks your membership and CoP numbers before businesses can see you."}
        </CardDescription>
      </CardHeader>
    </Card>
  );
}

/** `profile` is the saved profile, or null for a CA who has not saved one yet. */
function CaProfileForm({ profile }) {
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState(null);
  const [saved, setSaved] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(profileSchema),
    defaultValues: startingValues(profile),
  });

  async function onSubmit(values) {
    setServerError(null);
    setSaved(false);
    try {
      const updated = await saveCaProfile(values);
      queryClient.setQueryData(CA_PROFILE_KEY, updated);
      setSaved(true);
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Practice details</CardTitle>
        <CardDescription>Businesses see everything here except your CoP number.</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="membership_no"
              label="ICAI membership number"
              inputMode="numeric"
              error={errors.membership_no}
              {...register("membership_no")}
            />
            <FormField
              id="cop_number"
              label="Certificate of Practice number"
              error={errors.cop_number}
              {...register("cop_number")}
            />
            <FormField id="city" label="City" error={errors.city} {...register("city")} />
            <FormField
              id="years_experience"
              label="Years of experience"
              type="number"
              min={0}
              error={errors.years_experience}
              {...register("years_experience")}
            />
            <FormField
              id="capacity"
              label="Capacity (clients at a time)"
              type="number"
              min={1}
              error={errors.capacity}
              {...register("capacity")}
            />
          </div>
          <CheckboxGroup
            legend="Specializations"
            labels={CA_SPECIALIZATION_LABELS}
            error={errors.specializations}
            {...register("specializations")}
          />
          <CheckboxGroup
            legend="Languages"
            labels={CA_LANGUAGE_LABELS}
            error={errors.languages}
            {...register("languages")}
          />
          <div className="space-y-2">
            <Label htmlFor="about">About your practice (optional)</Label>
            <textarea
              id="about"
              rows={3}
              aria-invalid={!!errors.about}
              className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive"
              {...register("about")}
            />
            {errors.about && <p className="text-sm text-destructive">{errors.about.message}</p>}
          </div>
          {serverError && (
            <p role="alert" className="text-sm text-destructive">
              {serverError}
            </p>
          )}
          {saved && (
            <p role="status" className="text-sm text-muted-foreground">
              Profile saved.
            </p>
          )}
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving..." : "Save profile"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

/** One checkbox per code in `labels`; React Hook Form collects the ticked codes in an array. */
function CheckboxGroup({ legend, labels, error, ...inputProps }) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">{legend}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {Object.entries(labels).map(([code, text]) => (
          <label key={code} className="flex items-center gap-2 text-sm">
            <input type="checkbox" value={code} {...inputProps} />
            {text}
          </label>
        ))}
      </div>
      {error && <p className="text-sm text-destructive">{error.message}</p>}
    </fieldset>
  );
}

// The form's starting values: the saved profile, or empty fields for a new CA.
function startingValues(profile) {
  if (!profile) {
    return EMPTY_FORM;
  }
  return {
    membership_no: profile.membership_no,
    cop_number: profile.cop_number,
    city: profile.city,
    languages: profile.languages,
    specializations: profile.specializations,
    capacity: profile.capacity,
    years_experience: profile.years_experience,
    about: profile.about,
  };
}
