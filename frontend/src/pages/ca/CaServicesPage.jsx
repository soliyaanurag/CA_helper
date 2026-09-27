import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "@/api/client";
import {
  CA_SERVICES_KEY,
  saveCaServices,
  useCaProfile,
  useCaServices,
  useServices,
} from "@/api/marketplace";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { label, SERVICE_UNIT_LABELS } from "@/lib/labels";
import { comparedToMedian, typicalRangeText } from "@/lib/money";

// The same limits as CaServicePriceSchema in backend/app/schemas/marketplace.py.
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

function PriceMenu({ services, menu, verified }) {
  const queryClient = useQueryClient();
  const [rows, setRows] = useState(startingRows(services, menu));
  const [errors, setErrors] = useState({});
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
    setSaved(false);

    // Check every ticked row and collect what to send.
    const items = [];
    const newErrors = {};
    for (const service of services) {
      const row = rows[service.id];
      if (!row.offered) {
        continue;
      }
      const price = Number(row.price);
      if (row.price === "" || isNaN(price) || price < MIN_PRICE || price > MAX_PRICE) {
        newErrors[service.id] = PRICE_ERROR;
      } else {
        items.push({ service_id: service.id, price: row.price });
      }
    }
    setErrors(newErrors);
    if (Object.keys(newErrors).length > 0) {
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

function ServiceRow({ service, row, error, onChange }) {
  let hint = null;
  if (row.offered && row.price !== "") {
    hint = comparedToMedian(row.price, service.median_price);
  }

  return (
    <li className="space-y-2 rounded-lg border p-3">
      <label className="flex items-center gap-2 font-medium">
        <input
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
          aria-label={"Price for " + service.name}
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
      {error && <p className="text-sm text-destructive">{error}</p>}
    </li>
  );
}
