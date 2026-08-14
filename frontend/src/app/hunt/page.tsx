"use client";

import { useQuery } from "@tanstack/react-query";
import { JobCard } from "@/components/jobs/JobCard";
import { Alert } from "@/components/ui/Alert";
import { EmptyState } from "@/components/ui/EmptyState";
import { WorkspaceNav } from "@/components/workspace/WorkspaceNav";
import { getHuntPlan } from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { useRequireAuth } from "@/lib/auth";

export default function HuntPage() {
  const { user, loading } = useRequireAuth();
  const plan = useQuery({
    queryKey: ["hunt-plan", user?.id],
    enabled: Boolean(user),
    queryFn: getHuntPlan,
    staleTime: 60_000,
  });

  if (loading || !user) {
    return <div className="mx-auto max-w-4xl px-4 py-16 text-sm text-muted">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-3xl font-semibold text-ink">Today’s hunt</h1>
      <p className="mt-2 max-w-2xl text-sm text-muted">
        Five to eight junior-eligible roles posted in the last 48 hours. Apply on the employer site
        yourself — we never submit. This is not a streak counter.
      </p>
      <WorkspaceNav />
      {plan.isError ? (
        <Alert tone="error" title="Could not load plan" className="mt-6">
          {formatApiError(plan.error)}
        </Alert>
      ) : null}
      {plan.data?.empty_reason && !plan.data.results.length ? (
        <EmptyState
          className="mt-8"
          title="No fresh junior-eligible roles in 48 hours"
          description={plan.data.empty_reason}
          actions={[
            { label: "Open matches", href: "/matches", variant: "secondary" },
            { label: "Browse junior-eligible", href: "/jobs?career_stage=junior", variant: "ghost" },
          ]}
        />
      ) : null}
      <div className="mt-6 space-y-3">
        {plan.data?.results.map((job, i) => (
          <JobCard key={job.id} job={job} index={i} />
        ))}
      </div>
    </div>
  );
}
