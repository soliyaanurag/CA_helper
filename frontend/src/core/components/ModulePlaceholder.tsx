import { Badge } from "@/core/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/core/components/ui/card";

interface ModulePlaceholderProps {
  title: string;
  description: string;
  /** Owning member: "A", "B" or "C" (see docs/OWNERSHIP.md). */
  owner: "A" | "B" | "C";
  /** Tracker IDs that will replace this placeholder. */
  tasks: string[];
}

/** Stand-in page for a module that has no real screens yet. */
export function ModulePlaceholder({ title, description, owner, tasks }: ModulePlaceholderProps) {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <Card>
        <CardHeader>
          <CardTitle>Not built yet</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2 text-sm">
          <span>Owner: Member {owner}.</span>
          {tasks.length > 0 && <span>Next tasks:</span>}
          {tasks.map((task) => (
            <Badge key={task} variant="outline">
              {task}
            </Badge>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
