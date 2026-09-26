import { Link, useSearchParams } from "react-router";

import { errorMessage } from "@/api/client";
import { useServices, useVerifiedCas } from "@/api/marketplace";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  CA_LANGUAGE_LABELS,
  CA_SPECIALIZATION_LABELS,
  label,
  SERVICE_UNIT_LABELS,
} from "@/lib/labels";
import { comparedToMedian, formatRupees, typicalRangeText } from "@/lib/money";

const SELECT_CLASS =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

/**
 * /business/marketplace ("Find a CA"): verified CAs, most experienced first.
 * The filters live in the URL (?service=gstr_3b&language=hindi&city=pune&page=2),
 * so another page can link here with a filter already applied. With a service
 * chosen, the page shows its typical fee and each CA's price for it.
 */
export function MarketplacePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = {
    specialization: searchParams.get("specialization") ?? "",
    language: searchParams.get("language") ?? "",
    city: searchParams.get("city") ?? "",
    service: searchParams.get("service") ?? "",
    page: Number(searchParams.get("page") ?? 1),
  };
  const cas = useVerifiedCas(filters);
  const services = useServices();

  // The catalog service picked in the "Service" filter, if any.
  let chosenService = null;
  if (services.isSuccess && filters.service) {
    chosenService = services.data.find((service) => service.code === filters.service) || null;
  }

  /** Show `changes` (a new filter goes back to page 1); empty values leave the URL. */
  function show(changes) {
    const next = { ...filters, page: 1, ...changes };
    setSearchParams(
      Object.fromEntries(
        Object.entries(next).filter(([name, v]) => v && !(name === "page" && v === 1)),
      ),
    );
  }

  function onSearch(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    show(Object.fromEntries(form));
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Find a CA</h1>
        <p className="text-sm text-muted-foreground">
          Every CA listed here has been verified by our team.
        </p>
      </div>

      {/* key: the inputs show the URL's filters again after "Clear" or back/forward,
          and once the services have loaded (so the Service box can show its choice). */}
      <form
        key={searchParams.toString() + (services.isSuccess ? " loaded" : "")}
        className="grid gap-3 sm:grid-cols-2 sm:items-end lg:grid-cols-5"
        onSubmit={onSearch}
      >
        <div className="space-y-2">
          <Label htmlFor="service">Service</Label>
          <select
            id="service"
            name="service"
            defaultValue={filters.service}
            className={SELECT_CLASS}
          >
            <option value="">Any</option>
            {services.isSuccess &&
              services.data.map((service) => (
                <option key={service.id} value={service.code}>
                  {service.name}
                </option>
              ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="specialization">Specialization</Label>
          <select
            id="specialization"
            name="specialization"
            defaultValue={filters.specialization}
            className={SELECT_CLASS}
          >
            <option value="">Any</option>
            {Object.entries(CA_SPECIALIZATION_LABELS).map(([code, text]) => (
              <option key={code} value={code}>
                {text}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="language">Language</Label>
          <select
            id="language"
            name="language"
            defaultValue={filters.language}
            className={SELECT_CLASS}
          >
            <option value="">Any</option>
            {Object.entries(CA_LANGUAGE_LABELS).map(([code, text]) => (
              <option key={code} value={code}>
                {text}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="city">City</Label>
          <Input id="city" name="city" defaultValue={filters.city} placeholder="Any" />
        </div>
        <div className="flex gap-2">
          <Button type="submit">Search</Button>
          <Button type="button" variant="outline" onClick={() => setSearchParams({})}>
            Clear
          </Button>
        </div>
      </form>

      {cas.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {cas.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(cas.error)}
        </p>
      )}
      {chosenService && (
        <p className="text-sm">
          <span className="font-medium">Typical fee for {chosenService.name}: </span>
          {typicalRangeText(chosenService)} · {label(SERVICE_UNIT_LABELS, chosenService.unit)}
        </p>
      )}
      {cas.isSuccess && (
        <>
          <p className="text-sm text-muted-foreground">
            {cas.data.total === 1 ? "1 CA found" : `${cas.data.total} CAs found`}
          </p>
          {cas.data.items.length === 0 ? (
            <p className="text-sm">No verified CAs match these filters.</p>
          ) : (
            <ul className="grid gap-4 lg:grid-cols-2">
              {cas.data.items.map((ca) => (
                <li key={ca.id}>
                  <CaCard ca={ca} service={chosenService} search={searchParams.toString()} />
                </li>
              ))}
            </ul>
          )}
          <Pager data={cas.data} onPage={(page) => show({ ...filters, page })} />
        </>
      )}
    </div>
  );
}

// The whole card is a link to the CA's page. `service` is the catalog service
// chosen in the filter (or null); the card then shows this CA's price for it.
// `search` is the current filters, handed to the CA's page so its "Back to
// results" link keeps them.
function CaCard({ ca, service, search }) {
  const detailLink = "/business/marketplace/" + ca.id;

  let priceText = null;
  if (service && ca.price !== null) {
    priceText = formatRupees(ca.price) + " " + label(SERVICE_UNIT_LABELS, service.unit);
    const hint = comparedToMedian(ca.price, service.median_price);
    if (hint) {
      priceText = priceText + " · " + hint;
    }
  }

  return (
    <Link to={detailLink} state={{ search }} className="block h-full">
      <Card className="h-full cursor-pointer transition hover:shadow-md hover:ring-2 hover:ring-primary/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <h2>{ca.full_name}</h2>
            <Badge className="bg-green-100 text-green-700">Verified</Badge>
          </CardTitle>
          <CardDescription>
            {ca.city} · {ca.years_experience} {ca.years_experience === 1 ? "year" : "years"} of
            experience · ICAI no. {ca.membership_no}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex flex-wrap gap-1">
            {ca.specializations.map((code) => (
              <Badge key={code} variant="outline">
                {label(CA_SPECIALIZATION_LABELS, code)}
              </Badge>
            ))}
          </div>
          <p>
            <span className="text-muted-foreground">Languages: </span>
            {ca.languages.map((code) => label(CA_LANGUAGE_LABELS, code)).join(", ")}
          </p>
          {ca.about && <p>{ca.about}</p>}
          {priceText && (
            <p>
              <span className="text-muted-foreground">Fee for {service.name}: </span>
              <span className="font-medium">{priceText}</span>
            </p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}

function Pager({ data, onPage }) {
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  if (pages === 1) return null;
  return (
    <div className="flex items-center gap-3 text-sm">
      <Button variant="outline" disabled={data.page <= 1} onClick={() => onPage(data.page - 1)}>
        Previous
      </Button>
      <span>
        Page {data.page} of {pages}
      </span>
      <Button variant="outline" disabled={data.page >= pages} onClick={() => onPage(data.page + 1)}>
        Next
      </Button>
    </div>
  );
}
