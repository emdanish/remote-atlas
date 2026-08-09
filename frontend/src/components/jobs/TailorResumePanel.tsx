"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  downloadTailoredPdf,
  getTailoring,
  listResumes,
  regenerateTailoring,
  startTailoring,
  uploadResume,
  type Tailoring,
  type UserResume,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatApiError } from "@/lib/apiError";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { cn } from "@/lib/utils";
import { useToast } from "@/components/ui/Toaster";

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued…",
  analyzing_job: "Analyzing job requirements…",
  analyzing_resume: "Analyzing your resume…",
  matching_experience: "Matching your experience…",
  tailoring_sections: "Tailoring relevant sections…",
  checking_accuracy: "Checking factual accuracy…",
  preparing_preview: "Preparing your preview…",
  completed: "Ready",
  failed: "Failed",
};

function formatBlock(block: Record<string, unknown>): string {
  if (block.type === "job") {
    const head = [block.org, block.title, block.dates].filter(Boolean).join(" · ");
    const bullets = ((block.bullets as string[]) || []).map((b) => `• ${b}`).join("\n");
    return [head, bullets].filter(Boolean).join("\n");
  }
  if (block.type === "project") {
    const tech = ((block.technologies as string[]) || []).join(" · ");
    const bullets = ((block.bullets as string[]) || []).map((b) => `• ${b}`).join("\n");
    return [String(block.name || ""), tech, bullets].filter(Boolean).join("\n");
  }
  if (block.type === "education") {
    const head = [block.school, block.degree, block.dates].filter(Boolean).join(" · ");
    const details = ((block.details as string[]) || []).map((b) => `• ${b}`).join("\n");
    return [head, details].filter(Boolean).join("\n");
  }
  if (block.type === "skill_group") {
    const items = ((block.items as string[]) || []).join(", ");
    return `${block.category || "Skills"}: ${items}`;
  }
  return String(block.text || "");
}

function StructuredResume({
  title,
  tailored,
  highlight,
}: {
  title: string;
  tailored: NonNullable<Tailoring["tailored"]>;
  highlight?: boolean;
}) {
  const c = tailored.contact || {};
  const hasStructured =
    Boolean(tailored.skill_groups?.length) ||
    Boolean(tailored.experience?.length) ||
    Boolean(tailored.projects?.length) ||
    Boolean(tailored.education?.length) ||
    Boolean(tailored.summary);

  if (!hasStructured && tailored.sections?.length) {
    return (
      <div className="space-y-4 text-[13px] leading-relaxed text-ink">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</p>
        {c.name ? <p className="font-display text-lg font-semibold">{String(c.name)}</p> : null}
        {c.headline ? <p className="text-sm text-muted">{String(c.headline)}</p> : null}
        {tailored.summary ? (
          <div>
            <p className="text-[11px] font-semibold uppercase text-muted">Professional Summary</p>
            <p className={cn(highlight && "rounded bg-accent/10 px-1")}>{tailored.summary}</p>
          </div>
        ) : null}
        {tailored.sections.map((sec, i) => (
          <div key={`${sec.heading}-${i}`}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
              {sec.heading}
            </p>
            <div className="mt-1 space-y-2 whitespace-pre-wrap">
              {sec.blocks.map((b, j) => (
                <div
                  key={j}
                  className={cn(highlight && "rounded border-l-2 border-accent/40 pl-2")}
                >
                  {formatBlock(b as Record<string, unknown>)}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4 text-[13px] leading-relaxed text-ink">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</p>
      {c.name ? <p className="font-display text-lg font-semibold">{String(c.name)}</p> : null}
      {c.headline ? <p className="text-sm text-muted">{String(c.headline)}</p> : null}
      {[c.location, c.email, c.phone, ...(c.links || [])].filter(Boolean).length ? (
        <p className="text-xs text-muted">
          {[c.location, c.email, c.phone, ...(c.links || [])].filter(Boolean).join(" · ")}
        </p>
      ) : null}

      {tailored.summary ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Professional Summary
          </p>
          <p className={cn("mt-1", highlight && "rounded bg-accent/10 px-1")}>{tailored.summary}</p>
        </div>
      ) : null}

      {tailored.skill_groups?.length ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Technical Skills
          </p>
          <ul className="mt-1 space-y-1">
            {tailored.skill_groups.map((g) => (
              <li key={g.category}>
                <span className="font-semibold">{g.category}:</span>{" "}
                {(g.items || []).join(", ")}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {tailored.experience?.length ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Professional Experience
          </p>
          <div className="mt-2 space-y-3">
            {tailored.experience.map((e, i) => (
              <div key={i} className={cn(highlight && "rounded border-l-2 border-accent/40 pl-2")}>
                {e.org ? <p className="font-semibold">{e.org}</p> : null}
                <p className="text-xs text-muted italic">
                  {[e.title, e.location, e.dates].filter(Boolean).join(" · ")}
                </p>
                <ul className="mt-1 space-y-0.5">
                  {(e.bullets || []).map((b, j) => (
                    <li key={j}>• {b}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {tailored.projects?.length ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">Projects</p>
          <div className="mt-2 space-y-3">
            {tailored.projects.map((p, i) => (
              <div key={i} className={cn(highlight && "rounded border-l-2 border-accent/40 pl-2")}>
                <p className="font-semibold">{p.name}</p>
                {p.technologies?.length ? (
                  <p className="text-xs text-muted italic">{p.technologies.join(" · ")}</p>
                ) : null}
                <ul className="mt-1 space-y-0.5">
                  {(p.bullets || []).map((b, j) => (
                    <li key={j}>• {b}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {tailored.education?.length ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">Education</p>
          <div className="mt-2 space-y-3">
            {tailored.education.map((e, i) => (
              <div key={i}>
                {e.school ? <p className="font-semibold">{e.school}</p> : null}
                <p className="text-xs text-muted italic">
                  {[e.degree, e.dates].filter(Boolean).join(" · ")}
                </p>
                {(e.details || []).map((d, j) => (
                  <p key={j}>• {d}</p>
                ))}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Custom sections. The backend guarantees one entry per logical section. */}
      {(tailored.other_sections || [])
        .filter((s) => (s.items || []).length > 0)
        .map((s, i) => (
          <div key={`${s.heading}-${i}`}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
              {s.heading}
            </p>
            <ul className="mt-1 space-y-0.5">
              {(s.items || []).map((it, j) => (
                <li key={j}>• {it}</li>
              ))}
            </ul>
          </div>
        ))}
    </div>
  );
}

function ResumeDoc({
  title,
  excerpt,
  tailored,
  highlight,
}: {
  title: string;
  excerpt?: string | null;
  tailored?: Tailoring["tailored"];
  highlight?: boolean;
}) {
  if (
    tailored &&
    (tailored.skill_groups?.length ||
      tailored.experience?.length ||
      tailored.projects?.length ||
      tailored.education?.length ||
      tailored.summary ||
      tailored.sections?.length)
  ) {
    return <StructuredResume title={title} tailored={tailored} highlight={highlight} />;
  }
  return (
    <div className="space-y-2 text-[13px] leading-relaxed text-ink">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</p>
      <pre className="whitespace-pre-wrap font-sans text-[13px] text-ink/90">
        {excerpt || "No preview available."}
      </pre>
    </div>
  );
}

export function TailorResumePanel({ jobId }: { jobId: number }) {
  const { user, loading } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const [resumeId, setResumeId] = useState<number | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [tab, setTab] = useState<"side" | "original" | "tailored" | "changes">("side");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const resumes = useQuery({
    queryKey: ["resumes", user?.id],
    enabled: Boolean(user),
    queryFn: listResumes,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!resumes.data?.length) return;
    if (resumeId == null) {
      const primary = resumes.data.find((r) => r.is_primary) || resumes.data[0];
      setResumeId(primary.id);
    }
  }, [resumes.data, resumeId]);

  const run = useQuery({
    queryKey: ["tailoring", activeId],
    enabled: Boolean(activeId),
    queryFn: () => getTailoring(activeId!),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      if (s === "completed" || s === "failed") return false;
      return 1500;
    },
  });

  const onUpload = async (file: File) => {
    setUploading(true);
    setErr(null);
    try {
      const row = await uploadResume(file);
      await qc.invalidateQueries({ queryKey: ["resumes"] });
      setResumeId(row.id);
      toast.success("Resume saved for tailoring");
    } catch (e) {
      setErr(formatApiError(e));
    } finally {
      setUploading(false);
    }
  };

  const start = async () => {
    setBusy(true);
    setErr(null);
    try {
      const t = await startTailoring(jobId, resumeId);
      setActiveId(t.id);
      setTab("side");
    } catch (e) {
      setErr(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const onRegen = async () => {
    if (!activeId) return;
    setBusy(true);
    setErr(null);
    try {
      const t = await regenerateTailoring(activeId);
      setActiveId(t.id);
    } catch (e) {
      setErr(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const onDownload = async () => {
    if (!activeId) return;
    try {
      await downloadTailoredPdf(activeId);
      toast.success("Download started");
    } catch {
      toast.error("Could not download PDF");
    }
  };

  const data: Tailoring | undefined = run.data;
  const progressing =
    Boolean(activeId) && data?.status !== "completed" && data?.status !== "failed";

  const changes = data?.changes || data?.tailored?.changes || [];
  const panel = data?.match_panel || data?.tailored?.match_panel;

  const stageLabel = useMemo(() => {
    const s = data?.stage || "queued";
    return STAGE_LABELS[s] || s.replace(/_/g, " ");
  }, [data?.stage]);

  if (loading) return null;

  if (!user) {
    return (
      <div className="rounded-xl border border-line bg-elevated p-5 shadow-soft">
        <h2 className="font-display text-lg font-semibold text-ink">Tailor My Resume</h2>
        <p className="mt-2 text-sm text-muted">
          Sign in to tailor your existing resume for this job — without inventing experience.
        </p>
        <Button href="/login" size="sm" className="mt-3">
          Sign in
        </Button>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-line bg-elevated p-5 shadow-soft">
      <h2 className="font-display text-lg font-semibold text-ink">Tailor My Resume</h2>
      <p className="mt-2 text-sm text-muted">
        Rewrite wording and emphasize facts that already appear on your resume. Remote Atlas never
        invents jobs, skills, or metrics.
      </p>

      {err ? (
        <div className="mt-3">
          <Alert tone="error" title="Could not tailor" onDismiss={() => setErr(null)}>
            {err}
          </Alert>
        </div>
      ) : null}

      {!activeId || data?.status === "failed" ? (
        <div className="mt-4 space-y-3">
          {(resumes.data?.length || 0) > 0 ? (
            <div>
              <label className="text-xs font-medium text-muted">Your resume</label>
              <select
                className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink"
                value={resumeId ?? ""}
                onChange={(e) => setResumeId(Number(e.target.value))}
              >
                {(resumes.data as UserResume[]).map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.filename}
                    {r.is_primary ? " (primary)" : ""}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <p className="text-sm text-muted">
              No stored resume yet. Upload a PDF or DOCX (max 2MB).
            </p>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex cursor-pointer">
              <span className="sr-only">Upload resume</span>
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                className="hidden"
                disabled={uploading}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void onUpload(f);
                  e.target.value = "";
                }}
              />
              <span className="inline-flex h-9 items-center rounded-lg border border-line bg-paper px-3 text-sm font-medium text-ink hover:bg-elevated">
                {uploading ? "Uploading…" : "Upload resume"}
              </span>
            </label>
            <Button
              size="sm"
              onClick={() => void start()}
              disabled={busy || !resumeId}
            >
              {busy ? "Starting…" : "Tailor My Resume"}
            </Button>
          </div>
          {data?.status === "failed" && data.error_message ? (
            <p className="text-sm text-red-700">{data.error_message}</p>
          ) : null}
        </div>
      ) : null}

      {progressing ? (
        <div className="mt-5 space-y-3" aria-live="polite">
          <div className="h-1.5 overflow-hidden rounded-full bg-paper">
            <div className="h-full w-2/3 animate-pulse rounded-full bg-accent" />
          </div>
          <p className="text-sm font-medium text-ink">{stageLabel}</p>
          <p className="text-xs text-muted">This usually takes under a minute.</p>
        </div>
      ) : null}

      {data?.status === "completed" ? (
        <div className="mt-5 space-y-5">
          {data.validation?.fallback ? (
            <Alert tone="warning" title="Limited AI rewrite">
              {data.validation.message ||
                "Providers were unavailable. Original content was preserved with keyword matching only."}
            </Alert>
          ) : null}

          {panel ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <MatchCol title="Strong matches" items={panel.strong_matches} tone="good" />
              <MatchCol title="Emphasized" items={panel.emphasized} tone="accent" />
              <MatchCol title="Missing / unsupported" items={panel.missing} tone="warn" />
              <MatchCol title="Potential gaps" items={panel.potential_gaps} tone="muted" />
            </div>
          ) : null}
          {panel?.note ? (
            <p className="text-xs text-muted">{panel.note}</p>
          ) : null}

          {/* Tabs: mobile comparison */}
          <div className="flex flex-wrap gap-1 border-b border-line pb-2">
            {(
              [
                ["side", "Compare"],
                ["original", "Original"],
                ["tailored", "Tailored"],
                ["changes", "Changes"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-xs font-medium transition",
                  tab === id ? "bg-ink text-paper" : "text-muted hover:bg-paper",
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === "side" ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="max-h-[28rem] overflow-y-auto rounded-lg border border-line bg-paper p-4">
                <ResumeDoc title="Original" excerpt={data.original_excerpt} />
              </div>
              <div className="max-h-[28rem] overflow-y-auto rounded-lg border border-line bg-paper p-4">
                <ResumeDoc title="Tailored" tailored={data.tailored} highlight />
              </div>
            </div>
          ) : null}
          {tab === "original" ? (
            <div className="max-h-[28rem] overflow-y-auto rounded-lg border border-line bg-paper p-4">
              <ResumeDoc title="Original" excerpt={data.original_excerpt} />
            </div>
          ) : null}
          {tab === "tailored" ? (
            <div className="max-h-[28rem] overflow-y-auto rounded-lg border border-line bg-paper p-4">
              <ResumeDoc title="Tailored" tailored={data.tailored} highlight />
            </div>
          ) : null}
          {tab === "changes" ? (
            <ul className="max-h-[28rem] space-y-3 overflow-y-auto">
              {(changes as Array<Record<string, string>>).length ? (
                (changes as Array<Record<string, string>>).map((c, i) => (
                  <li
                    key={c.id || i}
                    className="rounded-lg border border-line bg-paper p-3 text-sm"
                  >
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                      {c.type || "modified"}
                      {c.section ? ` · ${c.section}` : ""}
                    </p>
                    {c.before ? (
                      <p className="mt-1 text-muted line-through decoration-red-400/60">
                        {c.before}
                      </p>
                    ) : null}
                    {c.after ? (
                      <p className="mt-1 text-ink">{c.after}</p>
                    ) : null}
                    {c.reason ? (
                      <p className="mt-2 text-xs text-accent">{c.reason}</p>
                    ) : null}
                  </li>
                ))
              ) : (
                <li className="text-sm text-muted">No line-level changes recorded.</li>
              )}
            </ul>
          ) : null}

          {(data.fidelity_note || data.validation?.fidelity_note) && (
            <p className="text-xs text-muted">
              {data.fidelity_note || data.validation?.fidelity_note}
              {typeof data.validation?.page_count === "number"
                ? ` · ${data.validation.page_count} page${data.validation.page_count === 1 ? "" : "s"}`
                : ""}
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => void onDownload()} disabled={!data.has_pdf}>
              Download Tailored Resume
            </Button>
            <Button size="sm" variant="secondary" onClick={() => void onRegen()} disabled={busy}>
              Regenerate
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setActiveId(null);
              }}
            >
              Start over
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function MatchCol({
  title,
  items,
  tone,
}: {
  title: string;
  items?: string[];
  tone: "good" | "accent" | "warn" | "muted";
}) {
  const toneCls =
    tone === "good"
      ? "border-emerald-200 bg-emerald-50/50"
      : tone === "warn"
        ? "border-amber-200 bg-amber-50/40"
        : tone === "accent"
          ? "border-accent/30 bg-accent/5"
          : "border-line bg-paper";
  return (
    <div className={cn("rounded-lg border p-3", toneCls)}>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</p>
      {items?.length ? (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {items.slice(0, 12).map((x) => (
            <li
              key={x}
              className="rounded border border-line/80 bg-elevated px-2 py-0.5 text-[11px] text-ink"
            >
              {x}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-xs text-muted">None listed</p>
      )}
    </div>
  );
}
