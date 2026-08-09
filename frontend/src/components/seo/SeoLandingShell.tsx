import Link from "next/link";
import { JobCard } from "@/components/jobs/JobCard";
import type { Job } from "@/lib/api/types";
import type { SeoTaxonomyItem } from "@/lib/api/seo";
import { ChevronRight } from "lucide-react";

type Crumb = { name: string; path: string };

type Props = {
  h1: string;
  intro: string;
  jobCount: number;
  freshnessDays: number;
  breadcrumb: Crumb[];
  jobs: Job[];
  page: number;
  pageSize: number;
  total: number;
  basePath: string;
  related?: SeoTaxonomyItem[];
  relatedTitle?: string;
};

export function SeoLandingShell({
  h1,
  intro,
  jobCount,
  freshnessDays,
  breadcrumb,
  jobs,
  page,
  pageSize,
  total,
  basePath,
  related,
  relatedTitle = "Related",
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasPrev = page > 1;
  const hasNext = page < totalPages;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <nav aria-label="Breadcrumb" className="mb-6 flex flex-wrap items-center gap-1 text-sm text-muted">
        {breadcrumb.map((b, i) => (
          <span key={b.path} className="inline-flex items-center gap-1">
            {i > 0 ? <ChevronRight className="h-3.5 w-3.5" aria-hidden /> : null}
            {i < breadcrumb.length - 1 ? (
              <Link href={b.path} className="hover:text-ink">
                {b.name}
              </Link>
            ) : (
              <span className="text-ink">{b.name}</span>
            )}
          </span>
        ))}
      </nav>

      <header className="max-w-3xl border-b border-line pb-8">
        <h1 className="font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          {h1}
        </h1>
        <p className="mt-4 text-base leading-7 text-muted">{intro}</p>
        <p className="mt-3 text-sm text-muted">
          <span className="font-semibold text-ink">{jobCount.toLocaleString()}</span> fresh roles
          in the active index
          {freshnessDays ? ` · ${freshnessDays}-day freshness window` : null}
        </p>
        <p className="mt-4">
          <Link href="/jobs" className="text-sm font-semibold text-accent hover:underline">
            Open full search with filters →
          </Link>
        </p>
      </header>

      <div className="mt-8 space-y-4">
        {jobs.length ? (
          jobs.map((job, i) => <JobCard key={job.id} job={job} index={i} />)
        ) : (
          <p className="text-muted">No matching jobs right now. Check back after the daily refresh.</p>
        )}
      </div>

      {totalPages > 1 ? (
        <nav
          className="mt-10 flex items-center justify-between border-t border-line pt-6 text-sm"
          aria-label="Pagination"
        >
          {hasPrev ? (
            <Link
              href={page - 1 <= 1 ? basePath : `${basePath}?page=${page - 1}`}
              className="font-semibold text-accent hover:underline"
              rel="prev"
            >
              ← Previous
            </Link>
          ) : (
            <span />
          )}
          <span className="text-muted">
            Page {page} of {totalPages}
          </span>
          {hasNext ? (
            <Link
              href={`${basePath}?page=${page + 1}`}
              className="font-semibold text-accent hover:underline"
              rel="next"
            >
              Next →
            </Link>
          ) : (
            <span />
          )}
        </nav>
      ) : null}

      {related?.length ? (
        <section className="mt-14 border-t border-line pt-10" aria-labelledby="related-seo">
          <h2 id="related-seo" className="font-display text-xl font-semibold text-ink">
            {relatedTitle}
          </h2>
          <ul className="mt-4 flex flex-wrap gap-2">
            {related.map((r) => (
              <li key={r.href}>
                <Link
                  href={r.href}
                  className="inline-flex rounded-md border border-line bg-elevated px-3 py-1.5 text-sm font-medium text-ink hover:border-accent hover:text-accent"
                >
                  {r.label}
                  <span className="ml-1.5 text-muted">({r.count})</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
