import { ModulePlaceholder } from "@/core/components/ModulePlaceholder";

export function OnboardingPage() {
  return (
    <ModulePlaceholder
      title="Business profile"
      description="Registration, regulatory profile with explanations, and NIC code."
      owner="A"
      tasks={["ONB-01", "ONB-02", "ONB-03"]}
    />
  );
}
