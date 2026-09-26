import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Join class names (clsx) and let later Tailwind classes win over earlier ones
 * (tailwind-merge), e.g. cn("px-2", isActive && "px-4") -> "px-4". The standard shadcn/ui helper.
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
