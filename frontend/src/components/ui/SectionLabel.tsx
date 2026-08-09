import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Small kicker above section headings — shared across marketing + product. */
export function SectionLabel({
  children,
  className,
  tone = "accent",
}: {
  children: ReactNode;
  className?: string;
  tone?: "accent" | "muted" | "light";
}) {
  const tones = {
    accent: "text-accent",
    muted: "text-muted",
    light: "text-teal-300/90",
  };
  return (
    <p className={cn("text-xs font-bold tracking-[0.18em]", tones[tone], className)}>
      {children}
    </p>
  );
}
