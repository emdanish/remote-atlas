"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { FileUp, Sparkles } from "lucide-react";
import { JobCard } from "@/components/jobs/JobCard";
import { Logo } from "@/components/brand/Logo";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import {
  completeOnboarding,
  createSavedSearch,
  getRecommendations,
  parseResume,
  type ResumeParseResponse,
} from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { useRequireAuth } from "@/lib/auth";
import { markOnboardingDoneLocal, storeSeedSkills } from "@/lib/onboarding";
import { uniqueLabels } from "@/lib/utils";

export default function OnboardingPage() {
  const { user, loading, refresh } = useRequireAuth("/login?next=/onboarding");
  const router = useRouter();
  const qc = useQueryClient();
  const [parsed, setParsed] = useState<ResumeParseResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<"upload" | "matches">("upload");
  const [huntStage, setHuntStage] = useState("junior");

  const recs = useQuery({
    queryKey: ["recommendations", user?.id, "onboarding"],
    enabled: Boolean(user) && step === "matches",
    queryFn: () => getRecommendations(8),
    staleTime: 60_000,
    retry: 1,
  });

  const resumeMutation = useMutation({
    mutationFn: (file: File) => parseResume(file),
    onSuccess: async (data) => {
      setParsed(data);
      setError(null);
      markOnboardingDoneLocal();
      await refresh();
      void qc.invalidateQueries({ queryKey: ["recommendations"] });
      setStep("matches");
    },
    onError: (err) => {
      setError(
        formatApiError(
          err,
          "Could not parse resume. You can still browse jobs and fill your profile later.",
        ),
      );
    },
  });

  async function finish(path: string, skipped = false) {
    const seeds = parsed?.seed_skills || parsed?.technologies?.slice(0, 2);
    if (seeds?.length) storeSeedSkills(seeds);
    try {
      await completeOnboarding({
        skipped,
        seed_skills: seeds,
        experience_level: huntStage,
      });
      await createSavedSearch({
        name: "Junior-eligible remote",
        query_params: {
          workplace: "remote",
          career_stage: huntStage === "internship" ? "internship" : "junior",
          junior_eligible: huntStage !== "internship",
          pakistan_friendly: true,
          posted_within: 7,
          skills: seeds?.join(", ") || undefined,
        },
        is_active: true,
      });
    } catch {
      /* non-blocking */
    }
    markOnboardingDoneLocal();
    await refresh();
    router.push(path);
  }

  if (loading || !user) {
    return (
      <div className="mx-auto max-w-lg px-4 py-20 text-center text-sm text-muted">
        Loading your workspace…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
      <Logo href="/" size="sm" className="mb-8 justify-center sm:justify-start" />

      <ol className="mb-8 flex gap-2 text-xs font-medium text-muted" aria-label="Progress">
        <li className={step === "upload" ? "text-accent" : "text-ink"}>1. Resume</li>
        <li aria-hidden>·</li>
        <li className={step === "matches" ? "text-accent" : ""}>2. Recommended roles</li>
      </ol>

      <div className="mb-8 text-center sm:text-left">
        <p className="text-xs font-semibold uppercase tracking-wider text-accent">Get started</p>
        <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          {step === "upload" ? "Add your resume" : "Roles matched to you"}
        </h1>
        <p className="mt-2 max-w-xl text-sm leading-6 text-muted sm:text-base">
          {step === "upload"
            ? "We extract skills and tech from your resume to rank roles. You can skip and fill your profile later — Jobs stays open either way."
            : "Ranked from the live catalogue. Apply only on official career pages."}
        </p>
      </div>

      {step === "upload" ? (
        <div className="rounded-xl border border-line bg-elevated p-6 shadow-soft sm:p-8">
          <fieldset className="mb-6 text-sm">
            <legend className="mb-2 font-medium text-ink">First-job stage</legend>
            <p className="mb-3 text-xs text-muted">
              We use this for junior-eligible search. We do not silently treat unlabeled senior roles as junior.
            </p>
            <div className="flex flex-wrap gap-3">
              {[
                { value: "internship", label: "Internship" },
                { value: "new_grad", label: "New graduate" },
                { value: "junior", label: "Junior / first role" },
              ].map((opt) => (
                <label key={opt.value} className="inline-flex items-center gap-2">
                  <input
                    type="radio"
                    name="hunt_stage"
                    checked={huntStage === opt.value}
                    onChange={() => setHuntStage(opt.value)}
                    className="accent-accent"
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="flex cursor-pointer flex-col items-center gap-3 rounded-lg border border-dashed border-line bg-paper/80 px-4 py-10 text-center transition-colors hover:border-accent/40">
            <FileUp className="h-8 w-8 text-accent" aria-hidden />
            <span className="text-sm font-medium text-ink">
              {resumeMutation.isPending ? "Parsing resume…" : "Drop PDF or text, or click to upload"}
            </span>
            <span className="text-xs text-muted">
              PDF, DOCX, TXT, MD · max 2MB · we extract text and rank roles — we never submit applications for you
            </span>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
              className="sr-only"
              disabled={resumeMutation.isPending}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  setError(null);
                  resumeMutation.mutate(file);
                }
              }}
            />
          </label>
          {error ? (
            <Alert tone="error" title="Resume parse failed" className="mt-4" onDismiss={() => setError(null)}>
              {error}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" onClick={() => void finish("/jobs", true)}>
                  Browse all jobs
                </Button>
                <Button size="sm" variant="ghost" onClick={() => void finish("/profile", true)}>
                  Edit profile manually
                </Button>
              </div>
            </Alert>
          ) : null}
          <div className="mt-6 flex flex-wrap justify-center gap-2 sm:justify-start">
            <Button variant="ghost" size="sm" onClick={() => void finish("/jobs", true)}>
              Skip for now
            </Button>
            <Button variant="secondary" size="sm" href="/profile">
              Paste skills on profile
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {parsed ? (
            <div className="rounded-xl border border-line bg-elevated p-5 shadow-soft">
              <div className="flex items-start gap-2">
                <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />
                <div>
                  <p className="text-sm font-medium text-ink">
                    Parsed {parsed.skills.length} skills · level {parsed.experience_level}
                  </p>
                  {parsed.summary ? (
                    <p className="mt-1 text-xs leading-relaxed text-muted">{parsed.summary}</p>
                  ) : null}
                  {parsed.seed_skills?.length ? (
                    <p className="mt-2 text-xs text-accent">
                      Top stack for chips: {parsed.seed_skills.join(", ")} (optional on Jobs filters)
                    </p>
                  ) : null}
                  {(parsed.technologies?.length || parsed.skills?.length) ? (
                    <ul className="mt-3 flex flex-wrap gap-1.5">
                      {[...uniqueLabels([...(parsed.technologies || []), ...(parsed.skills || [])])]
                    .slice(0, 12)
                    .map((t) => (
                      <li
                        key={t.toLowerCase()}
                        className="rounded-md bg-paper px-2 py-0.5 text-xs font-medium text-muted"
                      >
                        {t}
                      </li>
                    ))}
                    </ul>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}

          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <Button onClick={() => void finish("/matches")}>Explore all recommendations</Button>
            <Button variant="secondary" onClick={() => void finish("/jobs")}>
              Open personalised job search
            </Button>
            <Button variant="ghost" onClick={() => void finish("/alerts")}>
              Set pulse alerts
            </Button>
          </div>

          {recs.isLoading ? (
            <p className="text-sm text-muted">Loading matched roles…</p>
          ) : null}
          {recs.error ? (
            <Alert tone="error" title="Matches unavailable">
              {formatApiError(recs.error, "Could not load matches.")}{" "}
              <Link href="/jobs" className="font-medium underline">
                Browse jobs instead
              </Link>
            </Alert>
          ) : null}
          <div className="space-y-3">
            {recs.data?.results.slice(0, 6).map((job, i) => (
              <JobCard key={job.id} job={job} index={i} />
            ))}
          </div>
          {recs.data && recs.data.results.length === 0 ? (
            <div className="rounded-xl border border-dashed border-line bg-elevated p-6 text-sm text-muted">
              {recs.data.empty_reason || "No strong matches yet."}{" "}
              <Link href="/jobs" className="font-medium text-accent underline">
                Browse remote roles
              </Link>
              .
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
