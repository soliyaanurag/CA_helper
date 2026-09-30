import { errorMessage, useRegulatoryUpdates } from "@/api";
import { RegulatoryChangeCard } from "@/components/shared";

/**
 * /business/updates and /ca/updates ("Regulatory updates"): rule and due-date changes
 * found in the news that concern your forms (a CA: their active clients' forms),
 * newest first.
 */
export function RegulatoryUpdatesPage() {
  const updates = useRegulatoryUpdates();

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Regulatory updates</h1>
        <p className="text-sm text-muted-foreground">
          Changes to deadlines and filing rules found in the tax news, for the forms you file.
          Always check the official notice before you rely on one.
        </p>
      </div>
      {updates.isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {updates.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(updates.error)}
        </p>
      )}
      {updates.isSuccess && updates.data.length === 0 && (
        <p className="text-sm text-muted-foreground">No changes about your forms yet.</p>
      )}
      {updates.isSuccess && (
        <div className="space-y-4">
          {updates.data.map((change) => (
            <RegulatoryChangeCard key={change.id} change={change} />
          ))}
        </div>
      )}
    </div>
  );
}
