import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * A labelled input with its validation message, for React Hook Form:
 *
 *   <FormField id="email" label="Email" type="email" error={errors.email} {...register("email")} />
 *
 * `hint` is shown under the input while there is no error.
 */
export function FormField({ id, label, error, hint, ...inputProps }) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} aria-invalid={!!error} {...inputProps} />
      {error ? (
        <p className="text-sm text-destructive">{error.message}</p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}
