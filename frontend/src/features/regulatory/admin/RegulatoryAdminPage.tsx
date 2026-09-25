import { ModulePlaceholder } from "@/core/components/ModulePlaceholder";

export function RegulatoryAdminPage() {
  return (
    <ModulePlaceholder
      title="Regulatory news"
      description="Approve regulatory changes extracted from the news before alerts are sent."
      owner="B"
      tasks={["REG-01", "REG-02", "REG-03", "REG-04"]}
    />
  );
}
