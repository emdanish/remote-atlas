"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/Button";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex max-w-lg flex-col items-start gap-6 px-4 py-24 sm:px-6">
      <p className="text-xs font-bold tracking-[0.18em] text-accent">ERROR</p>
      <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">
        This page failed to finish loading.
      </h1>
      <p className="text-base leading-7 text-muted">
        The listing content may still be available. Retry, or browse the live catalogue.
      </p>
      <div className="flex flex-wrap gap-3">
        <Button type="button" size="md" onClick={() => reset()}>
          Try again
        </Button>
        <Button href="/jobs" variant="secondary" size="md">
          Browse jobs
        </Button>
      </div>
    </div>
  );
}
