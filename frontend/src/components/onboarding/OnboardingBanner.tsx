"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

/** Soft gate: non-blocking banner when profile/onboarding is incomplete. */
export function OnboardingBanner({ className }: { className?: string }) {
  const { user, loading } = useAuth();
  if (loading || !user) return null;
  const ob = user.onboarding;
  if (!ob || ob.onboarding_complete) return null;

  return (
    <div
      className={
        className ||
        "border-b border-accent/20 bg-accent-soft/60 px-4 py-2.5 text-sm text-ink"
      }
      role="status"
    >
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2">
        <p>
          Finish setup for better matches
          {ob.completion_percent ? ` · ${ob.completion_percent}%` : ""}. Upload a resume or add
          skills.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/onboarding" className="font-medium text-accent underline-offset-2 hover:underline">
            Continue onboarding
          </Link>
          <Link href="/profile" className="text-muted hover:text-ink">
            Edit profile
          </Link>
        </div>
      </div>
    </div>
  );
}
