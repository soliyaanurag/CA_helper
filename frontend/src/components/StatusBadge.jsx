import { Badge } from "@/components/ui/badge";
import { COMPLIANCE_STATUS_LABELS, label } from "@/lib/labels";

// A colour per filing status, so what needs attention stands out.
const COLOURS = {
  overdue: "bg-red-100 text-red-900",
  docs_pending: "bg-amber-100 text-amber-900",
  ready: "bg-sky-100 text-sky-900",
  with_ca: "bg-violet-100 text-violet-900",
  filed: "bg-green-100 text-green-900",
  filed_verified: "bg-green-100 text-green-900",
};

/** A filing's status (compliance_items.status) as a coloured badge. */
export function StatusBadge({ status }) {
  return (
    <Badge variant="secondary" className={COLOURS[status]}>
      {label(COMPLIANCE_STATUS_LABELS, status)}
    </Badge>
  );
}
