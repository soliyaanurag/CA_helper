import { Card, CardDescription, CardHeader, CardTitle } from "@/core/components/ui/card";

interface ModulePlaceholderProps {
  title: string;
  description: string;
}

/** Stand-in page for a module that has no real screens yet. */
export function ModulePlaceholder({ title, description }: ModulePlaceholderProps) {
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
