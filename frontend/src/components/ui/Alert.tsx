"use client";

import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type AlertTone = "error" | "success" | "info" | "warning";

const tones: Record<
  AlertTone,
  { box: string; icon: string; title: string; Icon: typeof AlertCircle }
> = {
  error: {
    box: "border-danger/25 bg-red-50/90 text-danger",
    icon: "text-danger",
    title: "text-danger",
    Icon: AlertCircle,
  },
  success: {
    box: "border-emerald-600/20 bg-emerald-50/90 text-emerald-900",
    icon: "text-emerald-700",
    title: "text-emerald-900",
    Icon: CheckCircle2,
  },
  info: {
    box: "border-accent/25 bg-accent-soft/50 text-ink",
    icon: "text-accent",
    title: "text-ink",
    Icon: Info,
  },
  warning: {
    box: "border-amber-600/25 bg-amber-50/90 text-amber-950",
    icon: "text-amber-700",
    title: "text-amber-950",
    Icon: AlertCircle,
  },
};

type Props = {
  tone?: AlertTone;
  title?: string;
  children: ReactNode;
  onDismiss?: () => void;
  className?: string;
  role?: "alert" | "status";
};

export function Alert({
  tone = "info",
  title,
  children,
  onDismiss,
  className,
  role = tone === "error" ? "alert" : "status",
}: Props) {
  const t = tones[tone];
  const Icon = t.Icon;
  return (
    <div
      role={role}
      className={cn(
        "flex gap-3 rounded-xl border px-3.5 py-3 text-sm shadow-soft sm:px-4 sm:py-3.5",
        t.box,
        className,
      )}
    >
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", t.icon)} aria-hidden />
      <div className="min-w-0 flex-1 leading-relaxed">
        {title ? <p className={cn("font-semibold", t.title)}>{title}</p> : null}
        <div className={cn(title ? "mt-0.5 opacity-95" : "")}>{children}</div>
      </div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded-md p-1 opacity-70 transition hover:bg-ink/5 hover:opacity-100"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
      ) : null}
    </div>
  );
}
