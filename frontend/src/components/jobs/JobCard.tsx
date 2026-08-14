"use client";

import Link from "next/link";
import { MapPin } from "lucide-react";
import { m, useReducedMotion } from "motion/react";
import GlareHover from "@/components/GlareHover";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { SaveJobButton } from "@/components/jobs/SaveJobButton";
import { TrackedApplyButton } from "@/components/jobs/TrackedApplyButton";
import type { Job } from "@/lib/api";
import {
  formatRelativeDate,
  officialApplyUrl,
  seniorityBadgeLabel,
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
      initial={reduceMotion ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={
        reduceMotion
          ? { duration: 0 }
          : { delay: Math.min(index * 0.02, 0.16), duration: 0.28, ease: [0.22, 1, 0.36, 1] }
      }
      className="rounded-xl border border-line bg-elevated shadow-soft transition-[border-color,box-shadow] duration-200 hover:border-accent/25 hover:shadow-lift"
    >
      <GlareHover
        className="rounded-xl"
        glareColor="#ffffff"
        glareOpacity={0.18}
        transitionDuration={480}
        disabled={Boolean(reduceMotion)}
      >
        <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1 space-y-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="accent">{job.source}</Badge>
              {job.source_kind_label || job.source_kind ? (
                <Badge>
                  {sourceKindLabel(job.source_kind, job.source_kind_label || undefined)}
                </Badge>
              ) : null}
              <Badge>{titleCase(job.workplace_type)}</Badge>
              {seniorityBadgeLabel(job) ? (
                <Badge>{seniorityBadgeLabel(job)}</Badge>
              ) : null}
              <time
                className="text-xs font-medium tabular-nums text-muted"
                dateTime={fresh || undefined}
              >
                {formatRelativeDate(fresh)}
              </time>
            </div>

            <h3 className="font-display text-lg font-semibold tracking-tight text-ink sm:text-xl">
              <Link
                href={`/jobs/${job.id}`}
                className="transition-colors hover:text-accent focus-visible:outline-none"
              >
                {job.title}
              </Link>
            </h3>

            <p className="text-sm font-semibold text-ink/85">{job.company_name}</p>

            {job.location_raw ? (
              <p className="inline-flex items-center gap-1.5 text-sm text-muted">
                <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden />
                <span className="line-clamp-1">{job.location_raw}</span>
              </p>
            ) : null}

            {reasons.length ? (
              <p className="text-xs font-medium text-accent">{reasons.join(" · ")}</p>
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
              <p className="max-w-2xl text-sm leading-relaxed text-muted line-clamp-2">
                {truncate(job.description_text, 160)}
              </p>
            ) : null}

            {tags.length ? (
              <ul className="flex flex-wrap gap-1.5 pt-0.5" aria-label="Skills">
                {tags.map((t) => (
                  <li
                    key={t.toLowerCase()}
                    className="rounded-md border border-line/80 bg-paper px-2 py-0.5 text-[11px] font-medium text-muted transition-colors hover:border-accent/30 hover:text-ink"
                  >
                    {t}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>

          <div className="flex shrink-0 flex-row items-stretch gap-2 sm:w-[7.5rem] sm:flex-col">
            {applyUrl ? (
              <TrackedApplyButton
                jobId={job.id}
                applyUrl={applyUrl}
                companyName={job.company_name}
                size="sm"
              />
            ) : null}
            <SaveJobButton jobId={job.id} size="sm" compact />
            <Button href={`/jobs/${job.id}`} variant="secondary" size="sm" className="flex-1 sm:flex-none">
              Details
            </Button>
          </div>
        </div>
      </GlareHover>
    </m.article>
  );
}
