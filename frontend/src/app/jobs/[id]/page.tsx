import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronRight, MapPin } from "lucide-react";
import { FitBriefPanel } from "@/components/jobs/FitBriefPanel";
import { TailorResumePanel } from "@/components/jobs/TailorResumePanel";
import { JobDescription } from "@/components/jobs/JobDescription";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { JobCard } from "@/components/jobs/JobCard";
import { SaveJobButton } from "@/components/jobs/SaveJobButton";
import { TrackedApplyButton } from "@/components/jobs/TrackedApplyButton";
import { getJob, searchJobs, SITE_URL } from "@/lib/api";
import {
  buildBreadcrumbJsonLd,
  buildJobPostingJsonLd,
  DEFAULT_FRESHNESS_DAYS,
  isJobIndexable,
  jobSeoDescription,
  jobSeoTitle,
  safeJsonLd,
} from "@/lib/seo";
import { companySeoHref, skillSeoHref } from "@/lib/seoTaxonomy";
import {
  formatRelativeDate,
  officialApplyUrl,
  sourceKindLabel,
  titleCase,
  uniqueLabels,
} from "@/lib/utils";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  try {
    const job = await getJob(Number(id));
    const title = jobSeoTitle(job);
    const description = jobSeoDescription(job);
    const indexable = isJobIndexable(job, DEFAULT_FRESHNESS_DAYS);
    const path = `/jobs/${job.id}`;
    return {
      title,
      description,
      alternates: { canonical: path },
      robots: indexable
        ? { index: true, follow: true }
        : { index: false, follow: true },
      openGraph: {
        title,
        description,
        url: `${SITE_URL}${path}`,
        type: "article",
        siteName: "Remote Atlas",
      },
      twitter: {
        card: "summary_large_image",
        title,
        description,
      },
    };
  } catch {
    return {
      title: "Job not found",
      robots: { index: false, follow: true },
    };
  }
}

export default async function JobDetailPage({ params }: Props) {
  const { id } = await params;
  const jobId = Number(id);
  if (!Number.isFinite(jobId)) notFound();

  let job;
  try {
    job = await getJob(jobId);
  } catch {
    notFound();
  }

  let related: Awaited<ReturnType<typeof searchJobs>>["results"] = [];
  try {
    const skills = (job.skills || job.tech_tags || []).slice(0, 3).join(",");
    const res = await searchJobs({
      q: job.title.split(" ").slice(0, 3).join(" "),
      skills: skills || undefined,
      page_size: 6,
      hybrid: true,
    });
    related = res.results.filter((j) => j.id !== job.id).slice(0, 4);
  } catch {
    /* optional */
  }

  const applyUrl = officialApplyUrl(job);
  const indexable = isJobIndexable(job, DEFAULT_FRESHNESS_DAYS);
  const postingLd = buildJobPostingJsonLd(job, {
    freshnessDays: DEFAULT_FRESHNESS_DAYS,
  });
  const breadcrumbLd = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Jobs", path: "/jobs" },
    { name: job.title, path: `/jobs/${job.id}` },
  ]);

  const tags = uniqueLabels(job.tech_tags, job.skills).slice(0, 16);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      {postingLd ? (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: safeJsonLd(postingLd) }}
        />
      ) : null}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: safeJsonLd(breadcrumbLd) }}
      />

      <nav aria-label="Breadcrumb" className="mb-6 flex flex-wrap items-center gap-1 text-sm text-muted">
        <Link href="/" className="hover:text-ink">
          Home
        </Link>
        <ChevronRight className="h-3.5 w-3.5" aria-hidden />
        <Link href="/jobs" className="hover:text-ink">
          Jobs
        </Link>
        <ChevronRight className="h-3.5 w-3.5" aria-hidden />
        <span className="text-ink line-clamp-1">{job.title}</span>
      </nav>

      {!indexable ? (
        <div
          className="mb-6 rounded-xl border border-line bg-elevated px-4 py-3 text-sm text-muted"
          role="status"
        >
          This listing is no longer in the active Remote Atlas index (
          {job.is_active === false ? "closed or removed from source" : "outside the freshness window"}
          ). It is kept for reference and is not offered as a current opportunity.
        </div>
      ) : null}

      <div className="grid gap-10 lg:grid-cols-[1fr_280px]">
        <article itemScope itemType="https://schema.org/JobPosting">
          <div className="flex flex-wrap gap-2">
            <Badge tone="accent">{job.source}</Badge>
            {job.source_kind || job.source_kind_label ? (
              <Badge>{sourceKindLabel(job.source_kind, job.source_kind_label || undefined)}</Badge>
            ) : null}
            <Badge>{titleCase(job.workplace_type)}</Badge>
            {job.career_stage !== "unknown" ? (
              <Badge>{titleCase(job.career_stage)}</Badge>
            ) : null}
            {job.employment_type ? <Badge>{job.employment_type}</Badge> : null}
          </div>
          <h1
            className="mt-4 font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl"
            itemProp="title"
          >
            {job.title}
          </h1>
          <p className="mt-2 text-lg font-medium text-ink/80" itemProp="hiringOrganization">
            <Link
              href={companySeoHref(job.company_name)}
              className="hover:text-accent hover:underline"
            >
              {job.company_name}
            </Link>
          </p>
          <div className="mt-3 flex flex-wrap gap-4 text-sm text-muted">
            {job.location_raw ? (
              <span className="inline-flex items-center gap-1.5">
                <MapPin className="h-4 w-4" aria-hidden />
                <span itemProp="jobLocation">{job.location_raw}</span>
              </span>
            ) : null}
            <span>
              Posted {formatRelativeDate(job.posted_at || job.first_seen_at)}
            </span>
          </div>

          {tags.length ? (
            <ul className="mt-6 flex flex-wrap gap-2" aria-label="Skills and technologies">
              {tags.map((t) => {
                const seoHref = skillSeoHref(t);
                const href = seoHref || `/jobs?skills=${encodeURIComponent(t)}`;
                return (
                  <li
                    key={t.toLowerCase()}
                    className="rounded-md border border-line bg-paper px-2.5 py-1 text-xs font-medium text-muted"
                  >
                    <Link href={href} className="hover:text-accent">
                      {t}
                    </Link>
                  </li>
                );
              })}
            </ul>
          ) : null}

          <div className="mt-10" itemProp="description">
            <JobDescription html={job.description_html} text={job.description_text} />
          </div>

          <div className="mt-10">
            <TailorResumePanel jobId={job.id} />
          </div>

          <div className="mt-10">
            <FitBriefPanel jobId={job.id} />
          </div>
        </article>

        <aside className="h-fit space-y-4 lg:sticky lg:top-24">
          <div className="rounded-xl border border-line bg-elevated p-5 shadow-soft">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted">
              Official application
            </p>
            <p className="mt-2 text-sm text-muted">
              Remote Atlas does not host applications. You apply on the company&apos;s system.
            </p>
            <div className="mt-4 flex flex-col gap-2">
              {applyUrl && indexable ? (
                <TrackedApplyButton
                  jobId={job.id}
                  applyUrl={applyUrl}
                  companyName={job.company_name}
                  size="md"
                  showDestination
                />
              ) : applyUrl && !indexable ? (
                <Button href={applyUrl} external variant="secondary" size="md">
                  View original posting
                </Button>
              ) : null}
              <SaveJobButton jobId={job.id} />
              {job.career_page_url ? (
                <Button href={job.career_page_url} external variant="ghost" size="sm">
                  Company careers
                </Button>
              ) : null}
            </div>
          </div>
          <div className="rounded-xl border border-line bg-paper p-5 text-sm">
            <p className="font-medium text-ink">Source transparency</p>
            <dl className="mt-3 space-y-2 text-muted">
              <div className="flex justify-between gap-2">
                <dt>Source</dt>
                <dd className="font-medium text-ink">{job.source}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt>Provenance</dt>
                <dd className="font-medium text-ink text-right">
                  {sourceKindLabel(job.source_kind, job.source_kind_label || undefined)}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt>Workplace</dt>
                <dd className="font-medium text-ink">{titleCase(job.workplace_type)}</dd>
              </div>
            </dl>
          </div>
          <p className="text-xs text-muted">
            <Link href="/jobs" className="font-medium text-accent hover:underline">
              Browse all fresh jobs
            </Link>
          </p>
        </aside>
      </div>

      {related.length ? (
        <section className="mt-16" aria-labelledby="related-roles-heading">
          <h2 id="related-roles-heading" className="font-display text-2xl font-semibold text-ink">
            Related roles
          </h2>
          <div className="mt-6 space-y-4">
            {related.map((j, i) => (
              <JobCard key={j.id} job={j} index={i} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
