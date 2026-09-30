import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import {
  ApiRequestError,
  CA_PROFILE_KEY,
  CA_SERVICES_KEY,
  errorMessage,
  saveCaProfile,
  saveCaServices,
  uploadCertificate,
  useCaProfile,
  useCaServices,
  useServices,
} from "@/api";
import { useAuth } from "@/auth";
import { FormField } from "@/components/shared";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
} from "@/components/ui";
import {
  CA_LANGUAGE_LABELS,
  CA_SPECIALIZATION_LABELS,
  CA_VERIFICATION_STATUS_LABELS,
  comparedToMedian,
  label,
  SERVICE_UNIT_LABELS,
  typicalRangeText,
} from "@/lib";

// --- CaProfilePage -----------------------------------------------------------------------------

// The same rules as the checks in backend/app/marketplace.py.
const profileSchema = z.object({
  membership_no: z.string().regex(/^[0-9]{6}$/, "Enter your 6-digit ICAI membership number."),
  cop_number: z.string().trim().min(1, "Enter your Certificate of Practice number.").max(20),
  city: z.string().trim().min(1, "Enter your city.").max(100),
  languages: z.array(z.string()).min(1, "Choose at least one language."),
  specializations: z.array(z.string()).min(1, "Choose at least one specialization."),
  capacity: z.coerce.number().int().min(1, "Enter a number from 1 to 1000.").max(1000),
  years_experience: z.coerce.number().int().min(0, "Enter a number from 0 to 70.").max(70),
  pro_bono_slots_per_month: z.coerce
    .number()
    .int()
    .min(0, "Enter a number from 0 to 1000.")
    .max(1000, "Enter a number from 0 to 1000."),
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
  pro_bono_slots_per_month: 0,
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

// Changing one of these fields sends a verified profile back for a new check (backend rule).
const IDENTITY_FIELDS = ["membership_no", "cop_number"];

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
          <CertificateCard profile={profile.data} />
          <CaProfileForm profile={profile.data} />
          {profile.data && <PreviewCard profile={profile.data} />}
        </>
      )}
    </div>
  );
}

function StatusCard({ profile }) {
  // No profile yet (null) -> no status.
  let status = null;
  if (profile) {
    status = profile.verification_status;
  }
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
        {status === "rejected" && profile.rejection_reason && (
          <p className="text-sm">
            <span className="font-medium">The admin's reason: </span>
            {profile.rejection_reason}
          </p>
        )}
      </CardHeader>
    </Card>
  );
}

/** Upload the Certificate of Practice: an admin checks it before verifying the CA. */
function CertificateCard({ profile }) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState(null);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const [sending, setSending] = useState(false);

  async function onUpload(event) {
    event.preventDefault();
    setError(null);
    setDone(false);
    setSending(true);
    try {
      const updated = await uploadCertificate(file);
      queryClient.setQueryData(CA_PROFILE_KEY, updated);
      setDone(true);
    } catch (uploadError) {
      setError(errorMessage(uploadError));
    }
    setSending(false);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Certificate of Practice</CardTitle>
        <CardDescription>
          {!profile
            ? "Save your profile first, then upload your certificate."
            : profile.has_certificate
              ? "Uploaded. Uploading a new one sends your profile back for verification."
              : "Upload your Certificate of Practice (PDF, JPG or PNG, up to 5 MB). An admin checks it before verifying you."}
        </CardDescription>
      </CardHeader>
      {profile && (
        <CardContent>
          <form className="flex flex-wrap items-center gap-3" onSubmit={onUpload}>
            <Label htmlFor="certificate" className="sr-only">
              Certificate file
            </Label>
            <Input
              id="certificate"
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              className="w-auto"
              onChange={(event) => setFile(firstFile(event.target.files))}
            />
            <Button type="submit" disabled={!file || sending}>
              {sending ? "Uploading..." : "Upload certificate"}
            </Button>
          </form>
          {error && (
            <p role="alert" className="mt-2 text-sm text-destructive">
              {error}
            </p>
          )}
          {done && (
            <p className="mt-2 text-sm text-muted-foreground">
              Certificate uploaded. An admin will check it.
            </p>
          )}
        </CardContent>
      )}
    </Card>
  );
}

/** How the saved profile looks on the businesses' "Find a CA" page. */
function PreviewCard({ profile }) {
  const { user } = useAuth();
  return (
    <Card>
      <CardHeader>
        <CardDescription>Preview: how businesses see you</CardDescription>
        <CardTitle>{user ? user.full_name : ""}</CardTitle>
        <CardDescription>
          {profile.city} · {profile.years_experience}{" "}
          {profile.years_experience === 1 ? "year" : "years"} of experience · ICAI no.{" "}
          {profile.membership_no}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <div className="flex flex-wrap gap-1">
          {profile.specializations.map((code) => (
            <Badge key={code} variant="outline">
              {label(CA_SPECIALIZATION_LABELS, code)}
            </Badge>
          ))}
        </div>
        <p>
          <span className="text-muted-foreground">Languages: </span>
          {profile.languages.map((code) => label(CA_LANGUAGE_LABELS, code)).join(", ")}
        </p>
        {profile.about && <p>{profile.about}</p>}
        {profile.verification_status !== "verified" && (
          <p className="text-xs text-muted-foreground">
            Businesses see this once an admin has verified you.
          </p>
        )}
      </CardContent>
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
    setError,
    control,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(profileSchema),
    defaultValues: startingValues(profile),
  });
  // A verified CA changing a number is told before saving that it needs a new check.
  const typed = useWatch({ control, name: IDENTITY_FIELDS });
  let needsNewCheck = false;
  if (profile && profile.verification_status === "verified") {
    for (let index = 0; index < IDENTITY_FIELDS.length; index++) {
      if (typed[index] !== profile[IDENTITY_FIELDS[index]]) {
        needsNewCheck = true;
      }
    }
  }

  async function onSubmit(values) {
    setServerError(null);
    setSaved(false);
    try {
      const updated = await saveCaProfile(values);
      queryClient.setQueryData(CA_PROFILE_KEY, updated);
      setSaved(true);
    } catch (error) {
      if (error instanceof ApiRequestError && error.code === "DUPLICATE_MEMBERSHIP_NO") {
        // Show it on the field it is about, not at the bottom of the form.
        setError("membership_no", { message: error.message }, { shouldFocus: true });
      } else {
        setServerError(errorMessage(error));
      }
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
            <FormField
              id="pro_bono_slots_per_month"
              label="Free (pro-bono) slots per month"
              type="number"
              min={0}
              hint="Engagements you take for free each month, for eligible businesses (0 = none)."
              error={errors.pro_bono_slots_per_month}
              {...register("pro_bono_slots_per_month")}
            />
          </div>
          {needsNewCheck && (
            <p className="rounded-lg bg-amber-100 p-3 text-sm text-amber-900">
              You changed your membership or CoP number: after saving, your profile goes back to an
              admin for verification and you leave the marketplace until then.
            </p>
          )}
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
          <label
            key={code}
            htmlFor={inputProps.name + "-" + code}
            className="flex items-center gap-2 text-sm"
          >
            <input id={inputProps.name + "-" + code} type="checkbox" value={code} {...inputProps} />
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
    pro_bono_slots_per_month: profile.pro_bono_slots_per_month || 0,
    about: profile.about,
  };
}

// The file the CA picked in a file input, or null if they picked none.
function firstFile(files) {
  if (files.length === 0) {
    return null;
  }
  return files[0];
}

// --- CaServicesPage ----------------------------------------------------------------------------

// The same limits as the checks in backend/app/marketplace.py.
const MIN_PRICE = 1;
const MAX_PRICE = 1000000;
const PRICE_ERROR = "Enter a price from 1 to 10,00,000.";

// /ca/services: the CA ticks the catalog services they offer and sets a price for
// each. Next to every price is the typical range across verified CAs.
export function CaServicesPage() {
  const profile = useCaProfile();
  const services = useServices();
  const menu = useCaServices();

  let content;
  if (profile.isPending || services.isPending || menu.isPending) {
    content = <p className="text-sm text-muted-foreground">Loading...</p>;
  } else if (profile.isError || services.isError || menu.isError) {
    const error = profile.error || services.error || menu.error;
    content = (
      <p role="alert" className="text-sm text-destructive">
        {errorMessage(error)}
      </p>
    );
  } else if (profile.data === null) {
    content = (
      <Card>
        <CardHeader>
          <CardTitle>Complete your profile first</CardTitle>
          <CardDescription>You can set your prices once your profile is saved.</CardDescription>
          <div>
            <Button asChild>
              <Link to="/ca/profile">Complete profile</Link>
            </Button>
          </div>
        </CardHeader>
      </Card>
    );
  } else {
    content = (
      <PriceMenu
        services={services.data}
        menu={menu.data}
        profile={profile.data}
        verified={profile.data.verification_status === "verified"}
      />
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Services & prices</h1>
        <p className="text-sm text-muted-foreground">
          Tick the services you offer and enter your fee. The typical range is worked out from the
          prices of all verified CAs.
        </p>
      </div>
      {content}
    </div>
  );
}

// The form's starting rows: { serviceId: { offered, price } } for every catalog service.
function startingRows(services, menu) {
  const rows = {};
  for (const service of services) {
    rows[service.id] = { offered: false, price: "" };
  }
  for (const item of menu.items) {
    // "750.00" -> "750", so the box shows what the CA typed.
    rows[item.service_id] = { offered: true, price: String(Number(item.price)) };
  }
  return rows;
}

function PriceMenu({ services, menu, profile, verified }) {
  const queryClient = useQueryClient();
  const [rows, setRows] = useState(startingRows(services, menu));
  const [errors, setErrors] = useState({});
  // Shown next to Save: the rows above may be far up the page (13 services).
  const [errorSummary, setErrorSummary] = useState(null);
  const [serverError, setServerError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  function updateRow(serviceId, changes) {
    setRows({ ...rows, [serviceId]: { ...rows[serviceId], ...changes } });
    setSaved(false);
  }

  async function onSave(event) {
    event.preventDefault();
    setServerError(null);
    setErrorSummary(null);
    setSaved(false);

    // Check every ticked row and collect what to send.
    const items = [];
    const newErrors = {};
    const wrongNames = [];
    for (const service of services) {
      const row = rows[service.id];
      if (!row.offered) {
        continue;
      }
      const price = Number(row.price);
      if (row.price === "" || isNaN(price) || price < MIN_PRICE || price > MAX_PRICE) {
        newErrors[service.id] = PRICE_ERROR;
        wrongNames.push(service.name);
      } else {
        items.push({ service_id: service.id, price: row.price });
      }
    }
    setErrors(newErrors);
    if (wrongNames.length > 0) {
      const count = wrongNames.length === 1 ? "1 price" : wrongNames.length + " prices";
      setErrorSummary("Fix " + count + ": " + wrongNames.join(", ") + ".");
      // Move to the first wrong price, which may be out of view.
      const firstWrong = document.getElementById(priceId(Object.keys(newErrors)[0]));
      if (firstWrong) {
        firstWrong.focus();
      }
      return;
    }

    setSaving(true);
    try {
      const savedMenu = await saveCaServices(items);
      queryClient.setQueryData(CA_SERVICES_KEY, savedMenu);
      // The typical ranges include this CA's prices, so load them again.
      queryClient.invalidateQueries({ queryKey: ["marketplace", "services"] });
      setSaved(true);
    } catch (error) {
      setServerError(errorMessage(error));
    }
    setSaving(false);
  }

  return (
    <form className="space-y-4" onSubmit={onSave} noValidate>
      {!verified && (
        <p className="text-sm text-muted-foreground">
          Businesses see your prices once an admin has verified your profile.
        </p>
      )}
      <SpecializationWarning services={services} rows={rows} profile={profile} />
      <ul className="space-y-3">
        {services.map((service) => (
          <ServiceRow
            key={service.id}
            service={service}
            row={rows[service.id]}
            error={errors[service.id]}
            onChange={(changes) => updateRow(service.id, changes)}
          />
        ))}
      </ul>
      {errorSummary && (
        <p role="alert" className="text-sm text-destructive">
          {errorSummary}
        </p>
      )}
      {serverError && (
        <p role="alert" className="text-sm text-destructive">
          {serverError}
        </p>
      )}
      {saved && (
        <p role="status" className="text-sm text-muted-foreground">
          Prices saved.
        </p>
      )}
      <Button type="submit" disabled={saving}>
        {saving ? "Saving..." : "Save prices"}
      </Button>
    </form>
  );
}

/**
 * A CA who prices a service should have its specialization (so businesses filtering by
 * it find them). Lists the ticked services whose specialization is missing, with a
 * button that adds them all to the profile.
 */
function SpecializationWarning({ services, rows, profile }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [adding, setAdding] = useState(false);

  const missing = [];
  for (const service of services) {
    const code = service.specialization;
    if (rows[service.id].offered && code && !profile.specializations.includes(code)) {
      if (!missing.includes(code)) missing.push(code);
    }
  }
  if (missing.length === 0) return null;

  async function onAdd() {
    setError(null);
    setAdding(true);
    try {
      const updated = await saveCaProfile({
        membership_no: profile.membership_no,
        cop_number: profile.cop_number,
        city: profile.city,
        languages: profile.languages,
        specializations: profile.specializations.concat(missing),
        capacity: profile.capacity,
        years_experience: profile.years_experience,
        about: profile.about,
      });
      queryClient.setQueryData(CA_PROFILE_KEY, updated);
    } catch (addError) {
      setError(errorMessage(addError));
    }
    setAdding(false);
  }

  return (
    <div role="note" className="space-y-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-900">
      <p>
        You price services that are not among your specializations:{" "}
        {missing.map((code) => label(CA_SPECIALIZATION_LABELS, code)).join(", ")}. Businesses
        filtering by specialization will not find you for them.
      </p>
      <Button type="button" size="sm" variant="outline" onClick={onAdd} disabled={adding}>
        {adding ? "Adding..." : "Add to specializations"}
      </Button>
      {error && <p className="text-destructive">{error}</p>}
    </div>
  );
}

// The id of a service's price box (the error summary moves the focus there).
function priceId(serviceId) {
  return "price-" + serviceId;
}

function ServiceRow({ service, row, error, onChange }) {
  let hint = null;
  if (row.offered && row.price !== "") {
    hint = comparedToMedian(row.price, service.median_price);
  }

  return (
    <li className="space-y-2 rounded-lg border p-3">
      <label htmlFor={"offer-" + service.id} className="flex items-center gap-2 font-medium">
        <input
          id={"offer-" + service.id}
          type="checkbox"
          checked={row.offered}
          onChange={(event) => onChange({ offered: event.target.checked })}
        />
        {service.name}
      </label>
      <p className="text-xs text-muted-foreground">{service.description}</p>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span>₹</span>
        <Input
          id={priceId(service.id)}
          aria-label={"Price for " + service.name}
          aria-describedby={error ? priceId(service.id) + "-error" : undefined}
          inputMode="decimal"
          className="w-32"
          value={row.price}
          disabled={!row.offered}
          aria-invalid={!!error}
          onChange={(event) => onChange({ price: event.target.value })}
        />
        <span>{label(SERVICE_UNIT_LABELS, service.unit)}</span>
        <span className="text-muted-foreground">Typical: {typicalRangeText(service)}</span>
        {hint && <span className="font-medium">{hint}</span>}
      </div>
      {error && (
        <p id={priceId(service.id) + "-error"} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </li>
  );
}
