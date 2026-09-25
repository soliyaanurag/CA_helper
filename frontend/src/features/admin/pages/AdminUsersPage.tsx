import { ModulePlaceholder } from "@/core/components/ModulePlaceholder";

export function AdminUsersPage() {
  return (
    <ModulePlaceholder
      title="Users & CAs"
      description="List, verify, suspend and remove users and CAs."
      owner="C"
      tasks={["ADM-01"]}
    />
  );
}
