import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "success" | "warn";
  className?: string;
}) {
  const tones = {
    neutral: "bg-paper text-muted border-line",
    accent: "bg-accent-soft text-accent-strong border-accent/20",
    success: "bg-accent-soft text-accent-strong border-accent/20",
    warn: "bg-amber-50 text-warn border-amber-200",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
