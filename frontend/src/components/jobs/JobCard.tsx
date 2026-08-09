"use client";

import Link from "next/link";
import { MapPin } from "lucide-react";
import { m, useReducedMotion } from "motion/react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { SaveJobButton } from "@/components/jobs/SaveJobButton";
import { TrackedApplyButton } from "@/components/jobs/TrackedApplyButton";
import type { Job } from "@/lib/api";
import {
  formatRelativeDate,
  officialApplyUrl,
  sourceKindLabel,
  titleCase,
  truncate,
  uniqueLabels,
} from "@/lib/utils";

export function JobCard({ job, index = 0 }: { job: Job; index?: number }) {
  const reduceMotion = useReducedMotion();
  const tags = uniqueLabels(job.tech_tags, job.skills).slice(0, 5);
  const fresh = job.posted_at || job.first_seen_at;
  const applyUrl = officialApplyUrl(job);
  const reasons = (job.match_reasons || []).slice(0, 3);

  return (
    <m.article
      initial={reduceMotion ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={
        reduceMotion
          ? { duration: 0 }
          : { delay: Math.min(index * 0.03, 0.24), duration: 0.35 }
      }
      className="group rounded-xl border border-line bg-elevated p-5 shadow-soft transition-shadow hover:shadow-lift"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="accent">{job.source}</Badge>
            {job.source_kind_label || job.source_kind ? (
              <Badge>{sourceKindLabel(job.source_kind, job.source_kind_label || undefined)}</Badge>
            ) : null}
            <Badge>{titleCase(job.workplace_type)}</Badge>
            {job.career_stage !== "unknown" ? (
              <Badge>{titleCase(job.career_stage)}</Badge>
            ) : null}
            <span className="text-xs text-muted">{formatRelativeDate(fresh)}</span>
          </div>
          <h3 className="font-display text-xl font-semibold tracking-tight text-ink">
            <Link href={`/jobs/${job.id}`} className="hover:text-accent">
              {job.title}
            </Link>
          </h3>
          <p className="text-sm font-medium text-ink/80">{job.company_name}</p>
          {job.location_raw ? (
            <p className="inline-flex items-center gap-1.5 text-sm text-muted">
              <MapPin className="h-3.5 w-3.5" aria-hidden />
              {job.location_raw}
            </p>
          ) : null}
          {reasons.length ? (
            <p className="text-xs font-medium text-accent">
              {reasons.join(" · ")}
            </p>
          ) : null}
          {typeof job.score === "number" ? (
            <p className="text-xs font-semibold tabular-nums text-ink">
              Atlas fit {Math.round(job.score)}
              {job.match_breakdown?.matched_skills?.length
                ? ` · ${job.match_breakdown.matched_skills.slice(0, 3).join(", ")}`
                : null}
            </p>
          ) : null}
          {job.description_text ? (
            <p className="max-w-2xl text-sm leading-relaxed text-muted">
              {truncate(job.description_text, 180)}
            </p>
          ) : null}
          {tags.length ? (
            <ul className="flex flex-wrap gap-1.5 pt-1">
              {tags.map((t) => (
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
        <div className="flex shrink-0 flex-row items-start gap-2 sm:flex-col">
          {applyUrl ? (
            <TrackedApplyButton
              jobId={job.id}
              applyUrl={applyUrl}
              companyName={job.company_name}
              size="sm"
            />
          ) : null}
          <SaveJobButton jobId={job.id} size="sm" compact />
          <Button href={`/jobs/${job.id}`} variant="secondary" size="sm">
            Details
          </Button>
        </div>
      </div>
    </m.article>
  );
}
