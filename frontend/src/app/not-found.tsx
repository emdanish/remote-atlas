import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/Button";

export const metadata: Metadata = {
  title: "Page not found",
  robots: { index: false, follow: true },
};

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-lg flex-col items-start gap-6 px-4 py-24 sm:px-6">
      <p className="text-xs font-bold tracking-[0.18em] text-accent">404</p>
      <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">
        We couldn&apos;t find that page.
      </h1>
      <p className="text-base leading-7 text-muted">
        The link may be outdated, or the job may have left the active index. Browse the live
        catalogue instead.
      </p>
      <div className="flex flex-wrap gap-3">
        <Button href="/jobs" size="md">
          Browse jobs
        </Button>
        <Link href="/" className="inline-flex h-10 items-center text-sm font-semibold text-accent">
          Home
        </Link>
      </div>
    </div>
  );
}
