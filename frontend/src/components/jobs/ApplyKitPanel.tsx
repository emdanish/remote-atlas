"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { getApplyKit } from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";

function copy(text: string) {
  void navigator.clipboard.writeText(text);
}

export function ApplyKitPanel({ jobId }: { jobId: number }) {
  const { user } = useAuth();
  const kit = useQuery({
    queryKey: ["apply-kit", jobId, user?.id],
    enabled: Boolean(user),
    queryFn: () => getApplyKit(jobId),
    staleTime: 60_000,
    retry: 1,
  });

  if (!user) {
    return (
      <div className="rounded-xl border border-line bg-elevated p-5">
        <h2 className="font-display text-lg font-semibold text-ink">Apply kit</h2>
        <p className="mt-2 text-sm text-muted">
          Sign in to copy a field card for the employer’s ATS. We never submit applications for you.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-line bg-elevated p-5 shadow-soft">
      <h2 className="font-display text-lg font-semibold text-ink">Apply kit</h2>
      <p className="mt-1 text-sm text-muted">
        We never submit applications for you. Paste into the official ATS, then apply yourself.
      </p>
      {kit.isError ? (
        <Alert tone="error" title="Could not build kit" className="mt-3">
          {formatApiError(kit.error)}
        </Alert>
      ) : null}
      {kit.data ? (
        <div className="mt-4 space-y-4 text-sm">
          {kit.data.skip_reason ? (
            <Alert tone="warning" title="Honesty check">
              {kit.data.skip_reason}
            </Alert>
          ) : null}
          <p className="text-muted">
            ATS time: {kit.data.ats_estimate.minutes_low}–{kit.data.ats_estimate.minutes_high} min
            {kit.data.ats_estimate.host ? ` · ${kit.data.ats_estimate.host}` : ""}.{" "}
            {kit.data.ats_estimate.note}
          </p>
          <div>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="font-semibold text-ink">Field card</h3>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() =>
                  copy(
                    Object.entries(kit.data.field_card)
                      .filter(([, v]) => v)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join("\n"),
                  )
                }
              >
                Copy
              </Button>
            </div>
            <dl className="grid gap-1 text-muted">
              {Object.entries(kit.data.field_card)
                .filter(([, v]) => v)
                .map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3">
                    <dt className="capitalize">{k.replace(/_/g, " ")}</dt>
                    <dd className="text-right font-medium text-ink">{v}</dd>
                  </div>
                ))}
            </dl>
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="font-semibold text-ink">Grounded note (~120 words)</h3>
              <Button type="button" size="sm" variant="ghost" onClick={() => copy(kit.data.cover_note)}>
                Copy
              </Button>
            </div>
            <p className="whitespace-pre-wrap text-muted">{kit.data.cover_note}</p>
          </div>
          <div>
            <h3 className="font-semibold text-ink">Likely short answers</h3>
            <ul className="mt-2 space-y-3">
              {kit.data.short_answers.map((a) => (
                <li key={a.prompt}>
                  <p className="font-medium text-ink">{a.prompt}</p>
                  <p className="mt-0.5 text-muted">{a.answer}</p>
                  <button
                    type="button"
                    className="mt-1 text-xs font-medium text-accent hover:underline"
                    onClick={() => copy(a.answer)}
                  >
                    Copy answer
                  </button>
                </li>
              ))}
            </ul>
          </div>
          {kit.data.skill_path?.days?.length ? (
            <div>
              <h3 className="font-semibold text-ink">
                7-day gap path
                {kit.data.skill_path.label ? ` · ${kit.data.skill_path.label}` : ""}
              </h3>
              <p className="mt-1 text-xs text-muted">
                Static catalog (roadmap.sh / freeCodeCamp). Not an LLM curriculum.
              </p>
              <ol className="mt-2 list-decimal space-y-1 pl-4 text-muted">
                {kit.data.skill_path.days.map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ol>
              {kit.data.skill_path.urls?.length ? (
                <ul className="mt-2 space-y-1">
                  {kit.data.skill_path.urls.map((u) => (
                    <li key={u}>
                      <a href={u} className="text-accent hover:underline" target="_blank" rel="noreferrer">
                        {u.replace(/^https?:\/\//, "")}
                      </a>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : kit.isLoading ? (
        <p className="mt-3 text-sm text-muted">Building kit from your profile…</p>
      ) : null}
    </div>
  );
}
