import { cn } from "@/lib/utils";
import type { InputHTMLAttributes } from "react";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-md border border-line bg-elevated px-3 text-ink placeholder:text-muted/80 shadow-soft focus:border-accent",
        className,
      )}
      {...props}
    />
  );
}
