import { Link } from "react-router";

import { errorMessage } from "@/api/client";
import { useServices } from "@/api/marketplace";
import { label, SERVICE_UNIT_LABELS } from "@/lib/labels";
import { formatRupees } from "@/lib/money";

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
