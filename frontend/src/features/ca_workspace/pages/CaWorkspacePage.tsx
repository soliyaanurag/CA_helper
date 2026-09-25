import { ModulePlaceholder } from "@/core/components/ModulePlaceholder";

export function CaWorkspacePage() {
  return (
    <ModulePlaceholder
      title="My clients"
      description="Multi-client dashboard, client calendars and marking items filed."
      owner="C"
      tasks={["CAW-01", "CAW-02"]}
    />
  );
}
