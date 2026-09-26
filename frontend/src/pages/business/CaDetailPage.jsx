import { Link, useLocation, useParams } from "react-router";

import { errorMessage } from "@/api/client";
import { useVerifiedCa } from "@/api/marketplace";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  CA_LANGUAGE_LABELS,
  CA_SPECIALIZATION_LABELS,
  label,
  SERVICE_UNIT_LABELS,
} from "@/lib/labels";
import { comparedToMedian, formatRupees, typicalRangeText } from "@/lib/money";

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
