import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router";

import {
  errorMessage,
  MY_ENGAGEMENTS_KEY,
  sendRequest,
  useRequestableFilings,
  useServices,
  useVerifiedCa,
  useVerifiedCas,
} from "@/api";
import { RatingSummary, Stars } from "@/components/shared";
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
  comparedToMedian,
  filingFormLabel,
  FORM_LABELS,
  formatDate,
  formatDateTime,
  formatRupees,
  label,
  SERVICE_UNIT_LABELS,
  typicalRangeText,
} from "@/lib";

// --- MarketplacePage ---------------------------------------------------------------------------

const SELECT_CLASS =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

/**
 * /business/marketplace ("Find a CA"): verified CAs. For a registered business the API
 * ranks them: CAs offering its own filings first (each card shows their prices for
 * them), then CAs in its city; CAs offering none of its filings are greyed and come last.
 * Otherwise most experienced first.
 * The filters live in the URL (?service=gstr_3b&language=hindi&city=pune&page=2),
 * so another page can link here with a filter already applied. With a service
 * chosen, the page shows its typical fee and each CA's price for it.
 */
export function MarketplacePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = {
    specialization: urlValue(searchParams, "specialization"),
    language: urlValue(searchParams, "language"),
    city: urlValue(searchParams, "city"),
    service: urlValue(searchParams, "service"),
    page: Number(urlValue(searchParams, "page") || 1),
  };
  const cas = useVerifiedCas(filters);
  const services = useServices();

  // The catalog service picked in the "Service" filter, if any.
  let chosenService = null;
  if (services.isSuccess && filters.service) {
    for (const service of services.data) {
      if (service.code === filters.service) {
        chosenService = service;
      }
    }
  }

  /** Show `changes` (a new filter goes back to page 1); empty values leave the URL. */
  function show(changes) {
    const next = { ...filters, page: 1, ...changes };
    const params = {};
    for (const name in next) {
      const value = next[name];
      // Leave out empty filters, and page 1 (the default).
      if (value && !(name === "page" && value === 1)) {
        params[name] = value;
      }
    }
    setSearchParams(params);
  }

  function onSearch(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    show({
      service: form.get("service"),
      specialization: form.get("specialization"),
      language: form.get("language"),
      city: form.get("city"),
    });
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

  // same_city is null before the business registers: then nothing is ranked or greyed.
  const ranked = ca.same_city !== null && ca.same_city !== undefined;
  const offersNone = ranked && ca.my_prices.length === 0;

  return (
    <Link to={detailLink} state={{ search }} className="block h-full">
      <Card
        className={
          "h-full cursor-pointer transition hover:shadow-md hover:ring-2 hover:ring-primary/40" +
          (offersNone ? " opacity-60" : "")
        }
      >
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <h2>{ca.full_name}</h2>
            <Badge className="bg-green-100 text-green-700">Verified</Badge>
            {ca.same_city && <Badge className="bg-sky-100 text-sky-900">Same city</Badge>}
            {ca.rating_count > 0 && (
              <span className="text-sm font-normal">
                <RatingSummary average={ca.rating_average} count={ca.rating_count} />
              </span>
            )}
          </CardTitle>
          <CardDescription>
            {ca.city} · {ca.years_experience} {ca.years_experience === 1 ? "year" : "years"} of
            experience · ICAI no. {ca.membership_no}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {ranked && ca.my_prices.length > 0 && (
            <p aria-label="Prices for your filings" className="font-medium">
              {ca.my_prices
                .map(
                  (item) =>
                    `${label(FORM_LABELS, item.form_code)} from ${formatRupees(item.price)}`,
                )
                .join(" · ")}
            </p>
          )}
          {offersNone && <p className="text-muted-foreground">Offers none of your filings.</p>}
          {ranked && ca.match_reasons.length > 0 && (
            <div aria-label="Why this CA">
              <p className="font-medium">
                Why this CA <span className="text-muted-foreground">(match {ca.match_score})</span>
              </p>
              <ul className="list-disc pl-5">
                {ca.match_reasons.map((reason) => (
                  <li key={reason.reason}>
                    {reason.reason}{" "}
                    <span className="text-muted-foreground">(+{reason.points})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
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

// One filter from the URL (?city=pune), or "" when it is not there.
function urlValue(searchParams, name) {
  const value = searchParams.get(name);
  if (value === null) {
    return "";
  }
  return value;
}

// --- CaDetailPage ------------------------------------------------------------------------------

// /business/marketplace/:caId: everything about one verified CA, opened from a card
// on "Find a CA". The card passes its search (the filters) so "Back" keeps them.
export function CaDetailPage() {
  const { caId } = useParams();
  const location = useLocation();
  const ca = useVerifiedCa(caId);

  let backLink = "/business/marketplace";
  if (location.state && location.state.search) {
    backLink = backLink + "?" + location.state.search;
  }

  return (
    <div className="max-w-3xl space-y-6">
      <Link to={backLink} className="text-sm text-primary underline-offset-4 hover:underline">
        ← Back to results
      </Link>

      {ca.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {ca.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(ca.error)}
        </p>
      )}
      {ca.isSuccess && <CaDetails ca={ca.data} />}
    </div>
  );
}

function CaDetails({ ca }) {
  return (
    <>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold">{ca.full_name}</h1>
          <Badge className="bg-green-100 text-green-700">Verified</Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          {ca.city} · {ca.years_experience} {ca.years_experience === 1 ? "year" : "years"} of
          experience · ICAI no. {ca.membership_no}
        </p>
      </div>

      <Button asChild>
        <Link to={"/business/marketplace/" + ca.id + "/request"}>Request this CA</Link>
      </Button>

      <Card>
        <CardHeader>
          <CardTitle>About</CardTitle>
          {ca.about ? (
            <CardDescription>{ca.about}</CardDescription>
          ) : (
            <CardDescription>
              This CA has not written anything about their practice.
            </CardDescription>
          )}
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="space-y-1">
            <p className="font-medium">Specializations</p>
            <div className="flex flex-wrap gap-1">
              {ca.specializations.map((code) => (
                <Badge key={code} variant="outline">
                  {label(CA_SPECIALIZATION_LABELS, code)}
                </Badge>
              ))}
            </div>
          </div>
          <p>
            <span className="font-medium">Languages: </span>
            {ca.languages.map((code) => label(CA_LANGUAGE_LABELS, code)).join(", ")}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Services & fees</CardTitle>
          <CardDescription>
            The CA's listed fee for each service, next to what verified CAs typically charge.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {ca.services.length === 0 ? (
            <p className="text-sm">This CA has not listed any prices yet.</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="border-b text-muted-foreground">
                <tr>
                  <th className="py-2 pr-4 font-medium">Service</th>
                  <th className="py-2 pr-4 font-medium">Fee</th>
                  <th className="py-2 font-medium">Typical</th>
                </tr>
              </thead>
              <tbody>
                {ca.services.map((service) => (
                  <ServiceRow key={service.id} service={service} />
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Ratings</CardTitle>
          <CardDescription>
            <RatingSummary average={ca.rating_average} count={ca.rating_count} />
          </CardDescription>
        </CardHeader>
        {ca.reviews && ca.reviews.length > 0 && (
          <CardContent>
            <ul className="space-y-3 text-sm">
              {ca.reviews.map((review) => (
                <li key={review.created_at}>
                  <Stars stars={review.stars} />{" "}
                  <span className="text-muted-foreground">{formatDateTime(review.created_at)}</span>
                  {review.review && <p>{review.review}</p>}
                </li>
              ))}
            </ul>
          </CardContent>
        )}
      </Card>
    </>
  );
}

function ServiceRow({ service }) {
  const hint = comparedToMedian(service.price, service.median_price);
  return (
    <tr className="border-b align-top">
      <td className="py-2 pr-4">{service.name}</td>
      <td className="py-2 pr-4">
        <span className="font-medium">{formatRupees(service.price)}</span>{" "}
        {label(SERVICE_UNIT_LABELS, service.unit)}
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </td>
      <td className="py-2 text-muted-foreground">{typicalRangeText(service)}</td>
    </tr>
  );
}

// --- RequestCaPage -----------------------------------------------------------------------------

// /business/marketplace/:caId/request: the business ticks the filings it wants this
// CA to do and sends the request. Filings that cannot be picked say why.
export function RequestCaPage() {
  const { caId } = useParams();
  const ca = useVerifiedCa(caId);
  const filings = useRequestableFilings(caId);

  let content;
  if (ca.isPending || filings.isPending) {
    content = <p className="text-sm text-muted-foreground">Loading...</p>;
  } else if (ca.isError || filings.isError) {
    content = (
      <p role="alert" className="text-sm text-destructive">
        {errorMessage(ca.error || filings.error)}
      </p>
    );
  } else if (filings.data === null) {
    content = (
      <p className="text-sm">
        <Link to="/business/onboarding" className="underline">
          Register your business
        </Link>{" "}
        first, so we know which filings you have.
      </p>
    );
  } else if (filings.data.length === 0) {
    content = <p className="text-sm">You have no filings due for the rest of this year.</p>;
  } else {
    content = <RequestForm caId={caId} filings={filings.data} />;
  }

  return (
    <div className="max-w-3xl space-y-6">
      <Link
        to={"/business/marketplace/" + caId}
        className="text-sm text-primary underline-offset-4 hover:underline"
      >
        ← Back to the CA
      </Link>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">
          Request {ca.isSuccess ? ca.data.full_name : "this CA"}
        </h1>
        <p className="text-sm text-muted-foreground">
          Tick the filings you want this CA to do. The CA can accept at these prices, send you a
          quote with new prices, or decline.
        </p>
      </div>
      {content}
    </div>
  );
}

// The price of the chosen service of one filing.
function priceOf(filing, serviceId) {
  for (const option of filing.options) {
    if (option.service_id === serviceId) {
      return Number(option.price);
    }
  }
  return 0;
}

function RequestForm({ caId, filings }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // { filing id: the chosen service id } for every ticked filing.
  const [chosen, setChosen] = useState({});
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);

  function toggle(filing) {
    const next = { ...chosen };
    if (next[filing.id]) {
      delete next[filing.id];
    } else {
      next[filing.id] = filing.options[0].service_id; // the first service by default
    }
    setChosen(next);
  }

  // Tick every filing of a quarter that can be picked (keeping choices already made).
  function selectAll(group) {
    const next = { ...chosen };
    for (const filing of group) {
      if (filing.blocked_reason === null && !next[filing.id]) {
        next[filing.id] = filing.options[0].service_id;
      }
    }
    setChosen(next);
  }

  function chooseService(filing, serviceId) {
    setChosen({ ...chosen, [filing.id]: serviceId });
  }

  let total = 0;
  for (const filing of filings) {
    if (chosen[filing.id]) {
      total = total + priceOf(filing, chosen[filing.id]);
    }
  }
  const nothingTicked = Object.keys(chosen).length === 0;

  async function onSend() {
    setError(null);
    const items = [];
    for (const filing of filings) {
      if (chosen[filing.id]) {
        items.push({ compliance_item_id: filing.id, service_id: chosen[filing.id] });
      }
    }
    if (items.length === 0) {
      return; // the button is disabled until a filing is ticked
    }

    setSending(true);
    try {
      await sendRequest(caId, items);
      queryClient.invalidateQueries({ queryKey: MY_ENGAGEMENTS_KEY });
      queryClient.invalidateQueries({ queryKey: ["marketplace", "requestable-filings"] });
      navigate("/business/engagements", { state: { sent: true } });
    } catch (sendError) {
      setError(errorMessage(sendError));
      setSending(false);
    }
  }

  // Filings this CA has not priced are listed apart, folded away.
  const offered = [];
  const notOffered = [];
  for (const filing of filings) {
    if (filing.options.length > 0) {
      offered.push(filing);
    } else {
      notOffered.push(filing);
    }
  }
  const quarters = groupByQuarter(offered);

  function filingRow(filing) {
    return (
      <li key={filing.id} className="rounded-lg border p-3 text-sm">
        <label htmlFor={"filing-" + filing.id} className="flex items-center gap-2 font-medium">
          <input
            id={"filing-" + filing.id}
            type="checkbox"
            value={filing.id}
            checked={Boolean(chosen[filing.id])}
            disabled={filing.blocked_reason !== null}
            onChange={() => toggle(filing)}
          />
          {filingFormLabel(filing.form_code, filing.period_label)} {filing.period_label}
          <span className="font-normal text-muted-foreground">
            · due {formatDate(filing.due_date)}
          </span>
        </label>
        {filing.blocked_reason ? (
          <p className="mt-1 text-muted-foreground">{filing.blocked_reason}</p>
        ) : (
          <FilingPrice
            filing={filing}
            serviceId={chosen[filing.id] || filing.options[0].service_id}
            onChoose={(serviceId) => chooseService(filing, serviceId)}
          />
        )}
      </li>
    );
  }

  return (
    <div className="space-y-4">
      {quarters.map((group) => (
        <section key={group.quarter} className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-medium">Due in {group.quarter}</h2>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => selectAll(group.filings)}
              disabled={allBlocked(group.filings)}
            >
              Select all in {group.quarter.split(" ")[0]}
            </Button>
          </div>
          <ul className="space-y-2">{group.filings.map(filingRow)}</ul>
        </section>
      ))}
      {notOffered.length > 0 && (
        <details className="rounded-lg border p-3">
          <summary className="cursor-pointer text-sm font-medium">
            Not offered by this CA ({notOffered.length})
          </summary>
          <ul className="mt-2 space-y-2">{notOffered.map(filingRow)}</ul>
        </details>
      )}

      <p className="text-sm font-medium">Total at the listed prices: {formatRupees(total)}</p>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={onSend} disabled={sending || nothingTicked}>
          {sending ? "Sending..." : "Send request"}
        </Button>
        <p className="text-sm text-muted-foreground">
          {nothingTicked ? "Tick at least one filing. " : ""}The CA has 48 hours to respond.
        </p>
      </div>
    </div>
  );
}

// The financial-year quarter a date falls in, e.g. "Q3 (Oct–Dec 2026)".
function quarterOf(isoDate) {
  const parts = isoDate.split("-"); // "2026-09-20" -> ["2026", "09", "20"]
  const year = parts[0];
  const month = Number(parts[1]);
  if (month >= 4 && month <= 6) {
    return "Q1 (Apr–Jun " + year + ")";
  }
  if (month >= 7 && month <= 9) {
    return "Q2 (Jul–Sep " + year + ")";
  }
  if (month >= 10) {
    return "Q3 (Oct–Dec " + year + ")";
  }
  return "Q4 (Jan–Mar " + year + ")";
}

// Groups filings by the quarter of their due date: [{ quarter: "Q2 (Jul–Sep 2026)",
// filings: [...] }, ...] in due-date order (the API sends the filings soonest first).
function groupByQuarter(filings) {
  const groups = [];
  for (const filing of filings) {
    const quarter = quarterOf(filing.due_date);
    const last = groups[groups.length - 1];
    if (last && last.quarter === quarter) {
      last.filings.push(filing);
    } else {
      groups.push({ quarter: quarter, filings: [filing] });
    }
  }
  return groups;
}

// True when no filing of the group can be picked (all are blocked).
function allBlocked(filings) {
  for (const filing of filings) {
    if (filing.blocked_reason === null) {
      return false;
    }
  }
  return true;
}

// The CA's price for a filing. If the CA offers several services for it (ITR),
// the business picks one.
function FilingPrice({ filing, serviceId, onChoose }) {
  if (filing.options.length === 1) {
    const option = filing.options[0];
    return (
      <p className="mt-1">
        {option.name}: <span className="font-medium">{formatRupees(option.price)}</span>
      </p>
    );
  }
  return (
    <select
      aria-label={"Service for " + filing.period_label}
      className="mt-1 h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
      value={serviceId}
      onChange={(event) => onChoose(event.target.value)}
    >
      {filing.options.map((option) => (
        <option key={option.service_id} value={option.service_id}>
          {option.name}: {formatRupees(option.price)}
        </option>
      ))}
    </select>
  );
}

// --- TypicalFeesPage ---------------------------------------------------------------------------

// /business/fees: what CAs on the platform typically charge for each service
// (lowest, middle and highest price of the verified CAs who offer it).
export function TypicalFeesPage() {
  const services = useServices();

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Typical fees</h1>
        <p className="text-sm text-muted-foreground">
          The fees listed by verified CAs on our platform. A range is shown once at least three CAs
          offer the service.
        </p>
      </div>

      {services.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {services.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(services.error)}
        </p>
      )}
      {services.isSuccess && (
        <table className="w-full text-left text-sm">
          <thead className="border-b text-muted-foreground">
            <tr>
              <th className="py-2 pr-4 font-medium">Service</th>
              <th className="py-2 pr-4 font-medium">Lowest</th>
              <th className="py-2 pr-4 font-medium">Median</th>
              <th className="py-2 pr-4 font-medium">Highest</th>
              <th className="py-2 pr-4 font-medium">CAs</th>
              <th className="py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {services.data.map((service) => (
              <tr key={service.id} className="border-b">
                <td className="py-2 pr-4">
                  {service.name}
                  <span className="text-muted-foreground">
                    {" "}
                    ({label(SERVICE_UNIT_LABELS, service.unit)})
                  </span>
                </td>
                {service.median_price === null ? (
                  <td colSpan={3} className="py-2 pr-4 text-muted-foreground">
                    Not enough data yet
                  </td>
                ) : (
                  <>
                    <td className="py-2 pr-4">{formatRupees(service.min_price)}</td>
                    <td className="py-2 pr-4">{formatRupees(service.median_price)}</td>
                    <td className="py-2 pr-4">{formatRupees(service.max_price)}</td>
                  </>
                )}
                <td className="py-2 pr-4">{service.ca_count}</td>
                <td className="py-2">
                  <Link
                    to={"/business/marketplace?service=" + service.code}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    Find a CA
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
