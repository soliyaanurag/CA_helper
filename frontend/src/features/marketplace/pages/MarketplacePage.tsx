import { ModulePlaceholder } from "@/core/components/ModulePlaceholder";

export function MarketplacePage() {
  return (
    <ModulePlaceholder
      title="Find a CA"
      description="CA listings filtered by form, requests and engagements."
      owner="C"
      tasks={["MKT-01", "MKT-02", "MKT-03"]}
    />
  );
}
