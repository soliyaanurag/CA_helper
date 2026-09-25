import { ModulePlaceholder } from "@/core/components/ModulePlaceholder";

export function AlertsPage() {
  return (
    <ModulePlaceholder
      title="Notification settings"
      description="Deadline reminders (email + tray) and the penalty estimator."
      owner="B"
      tasks={["ALR-01"]}
    />
  );
}
