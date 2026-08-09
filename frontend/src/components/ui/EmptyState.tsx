import Link from "next/link";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

type Action = {
  href?: string;
  label: string;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "ghost";
};

export function EmptyState({
  title,
  description,
  actions,
  className,
  children,
}: {
  title: string;
  description?: string;
  actions?: Action[];
  className?: string;
  children?: ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-dashed border-line bg-elevated px-6 py-12 text-center sm:px-10",
        className,
      )}
      role="status"
    >
      <p className="font-display text-xl font-semibold tracking-tight text-ink">{title}</p>
      {description ? (
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">{description}</p>
      ) : null}
      {children}
      {actions?.length ? (
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          {actions.map((a) =>
            a.href ? (
              <Button key={a.label} href={a.href} variant={a.variant ?? "primary"} size="sm">
                {a.label}
              </Button>
            ) : (
              <Button
                key={a.label}
                type="button"
                variant={a.variant ?? "secondary"}
                size="sm"
                onClick={a.onClick}
              >
                {a.label}
              </Button>
            ),
          )}
        </div>
      ) : null}
      {!actions?.length && !children ? (
        <p className="mt-4 text-sm">
          <Link href="/jobs" className="font-semibold text-accent hover:underline">
            Browse jobs
          </Link>
        </p>
      ) : null}
    </div>
  );
}
