import { ModulePlaceholder } from "@/core/components/ModulePlaceholder";

export function CompliancePage() {
  return (
    <ModulePlaceholder
      title="Compliance calendar"
      description="Filing obligations, month/list calendar, item pages and the home dashboard."
      owner="A"
      tasks={["COM-01", "COM-02", "COM-03", "COM-04"]}
    />
  );
}
