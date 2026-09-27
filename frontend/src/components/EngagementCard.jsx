import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate, formatDateTime } from "@/lib/dates";
import { ENGAGEMENT_STATUS_LABELS, FORM_LABELS, label } from "@/lib/labels";
import { formatRupees } from "@/lib/money";

// Badge colour for each engagement status.
const STATUS_COLORS = {
  requested: "bg-amber-100 text-amber-800",
  quoted: "bg-blue-100 text-blue-800",
  active: "bg-green-100 text-green-700",
  completed: "bg-gray-100 text-gray-700",
  declined: "bg-red-100 text-red-700",
  expired: "bg-gray-100 text-gray-700",
  cancelled: "bg-gray-100 text-gray-700",
};

// Adds up one kind of price of all filings ("listed_price", "quoted_price" or "agreed_price").
function total(items, priceName) {
  let sum = 0;
  for (const item of items) {
    sum = sum + Number(item[priceName]);
  }
  return sum;
}

/**
 * One engagement as a card: who it is with, its status, and each filing with its
 * prices. Used by the business's and the CA's "My engagements" pages. `title` is
 * the other side's name; `children` are the action buttons for the current status.
 */
export function EngagementCard({ engagement, title, children }) {
  const items = engagement.items;
  const hasQuote = items.length > 0 && items[0].quoted_price !== null;
  const hasAgreed = items.length > 0 && items[0].agreed_price !== null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <h3>{title}</h3>
          <Badge className={STATUS_COLORS[engagement.status]}>
            {label(ENGAGEMENT_STATUS_LABELS, engagement.status)}
          </Badge>
        </CardTitle>
        <CardDescription>Requested {formatDateTime(engagement.requested_at)}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <table className="w-full text-left">
          <thead className="border-b text-muted-foreground">
            <tr>
              <th className="py-1 pr-3 font-medium">Filing</th>
              <th className="py-1 pr-3 font-medium">Service</th>
              <th className="py-1 pr-3 font-medium">Listed price</th>
              {hasQuote && <th className="py-1 pr-3 font-medium">Quoted price</th>}
              {hasAgreed && <th className="py-1 font-medium">Agreed price</th>}
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b">
                <td className="py-1 pr-3">
                  {item.form_code ? label(FORM_LABELS, item.form_code) : "Removed filing"}{" "}
                  {item.period_label}
                  {item.due_date && (
                    <span className="text-muted-foreground">
                      {" "}
                      · due {formatDate(item.due_date)}
                    </span>
                  )}
                </td>
                <td className="py-1 pr-3">{item.service_name}</td>
                <td className="py-1 pr-3">{formatRupees(item.listed_price)}</td>
                {hasQuote && <td className="py-1 pr-3">{formatRupees(item.quoted_price)}</td>}
                {hasAgreed && <td className="py-1">{formatRupees(item.agreed_price)}</td>}
              </tr>
            ))}
          </tbody>
          <tfoot className="font-medium">
            <tr>
              <td className="py-1 pr-3" colSpan={2}>
                Total
              </td>
              <td className="py-1 pr-3">{formatRupees(total(items, "listed_price"))}</td>
              {hasQuote && (
                <td className="py-1 pr-3">{formatRupees(total(items, "quoted_price"))}</td>
              )}
              {hasAgreed && <td className="py-1">{formatRupees(total(items, "agreed_price"))}</td>}
            </tr>
          </tfoot>
        </table>
        {engagement.quote_reason && (
          <p>
            <span className="font-medium">Reason for the quote: </span>
            {engagement.quote_reason}
          </p>
        )}
        {children}
      </CardContent>
    </Card>
  );
}
