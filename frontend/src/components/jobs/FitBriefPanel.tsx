"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { getFitBrief } from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { cn, uniqueLabels } from "@/lib/utils";

function Bar({ label, value, max = 35 }: { label: string; value: number; max?: number }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted">
        <span>{label}</span>
        <span className="tabular-nums text-ink">{value.toFixed(0)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-paper">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function FitBriefPanel({ jobId }: { jobId: number }) {
  const { user, loading } = useAuth();
  const hasSkills = Boolean(
    user?.profile?.skills?.length || user?.profile?.technologies?.length,
  );

  const brief = useQuery({
    queryKey: ["fit-brief", jobId, user?.id],
    enabled: Boolean(user) && hasSkills,
    queryFn: () => getFitBrief(jobId),
    staleTime: 60_000,
    retry: 1,
  });

  if (loading) return null;

  if (!user) {
    return (
      <div className="rounded-xl border border-line bg-elevated p-5 shadow-soft">
        <h2 className="font-display text-lg font-semibold text-ink">Atlas Fit Brief</h2>
        <p className="mt-2 text-sm text-muted">
          Sign in and add skills to see an explainable apply score for this role.
        </p>
        <Button href="/login" size="sm" className="mt-3">
          Sign in
        </Button>
      </div>
    );
  }

  if (!hasSkills) {
    return (
      <div className="rounded-xl border border-line bg-elevated p-5 shadow-soft">
        <h2 className="font-display text-lg font-semibold text-ink">Atlas Fit Brief</h2>
        <p className="mt-2 text-sm text-muted">
          Upload a resume or add technologies on your profile to unlock a personalised ledger.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button href="/onboarding" size="sm">
            Resume onboarding
          </Button>
          <Button href="/profile" size="sm" variant="secondary">
            Edit profile
          </Button>
        </div>
      </div>
    );
  }

  if (brief.isLoading) {
    return (
      <div className="rounded-xl border border-line bg-elevated p-5 shadow-soft">
        <p className="text-sm text-muted">Building Fit Brief…</p>
      </div>
    );
  }

  if (brief.isError || !brief.data) {
    return (
      <Alert
        tone="error"
        title="Fit Brief unavailable"
        className="shadow-soft"
      >
        <p>{formatApiError(brief.error, "Could not score this role. You can still apply.")}</p>
        <Button size="sm" variant="secondary" className="mt-3" onClick={() => void brief.refetch()}>
          Retry
        </Button>
      </Alert>
    );
  }

  const data = brief.data;
  const bd = data.breakdown;
  const verdictTone =
    data.verdict === "apply"
      ? "text-accent"
      : data.verdict === "maybe"
        ? "text-ink"
        : "text-muted";

  return (
    <section className="rounded-xl border border-line bg-elevated p-5 shadow-soft sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-accent">
            Atlas Fit Brief
          </p>
          <h2 className="mt-1 font-display text-xl font-semibold text-ink">
            Score {Math.round(data.score)}
            <span className={cn("ml-2 text-sm font-medium capitalize", verdictTone)}>
              · {data.verdict}
            </span>
          </h2>
        </div>
        <span className="rounded-md bg-paper px-2 py-1 text-xs text-muted">
          {data.provider === "ai" ? "AI + ledger" : "Ledger fallback"}
        </span>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-muted">{data.narrative}</p>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <Bar label="Skills" value={bd.skill} max={35} />
        <Bar label="Role title" value={bd.role} max={20} />
        <Bar label="Seniority" value={bd.seniority} max={12} />
        <Bar label="Remote fit" value={bd.remote} max={12} />
        <Bar label="Pakistan affinity" value={bd.pakistan} max={10} />
        <Bar label="Freshness" value={bd.freshness} max={10} />
      </div>

      {(bd.matched_skills?.length || bd.missing_skills?.length) ? (
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {bd.matched_skills?.length ? (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-accent">Matched</p>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {uniqueLabels(bd.matched_skills).map((s) => (
                  <li
                    key={`match-${s.toLowerCase()}`}
                    className="rounded-md bg-accent-soft px-2 py-0.5 text-xs text-accent-strong"
                  >
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {bd.missing_skills?.length ? (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted">Gaps</p>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {uniqueLabels(bd.missing_skills).map((s) => (
                  <li
                    key={`gap-${s.toLowerCase()}`}
                    className="rounded-md bg-paper px-2 py-0.5 text-xs text-muted"
                  >
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      {data.tips?.length ? (
        <ul className="mt-5 space-y-1.5 border-t border-line pt-4 text-sm text-muted">
          {uniqueLabels(data.tips).map((t, i) => (
            <li key={`tip-${i}-${t.slice(0, 24)}`} className="flex gap-2">
              <span className="text-accent" aria-hidden>
                ·
              </span>
              <span>{t}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
