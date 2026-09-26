import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** Stand-in page for a feature that has no real screens yet. */
export function Placeholder({ title, description }) {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <Card>
        <CardHeader>
          <CardTitle>Not built yet</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}
