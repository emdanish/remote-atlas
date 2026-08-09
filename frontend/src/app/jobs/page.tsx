"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  parseAsBoolean,
  parseAsInteger,
  parseAsString,
  useQueryStates,
} from "nuqs";
import { ArrowUpDown, SlidersHorizontal, X } from "lucide-react";
import { JobCard } from "@/components/jobs/JobCard";
import { JobCardSkeleton } from "@/components/jobs/JobCardSkeleton";
import {
  SearchFilters,
  type SearchFilterState,
} from "@/components/search/SearchFilters";
import { Button } from "@/components/ui/Button";
import { searchJobs } from "@/lib/api";
import { formatApiError } from "@/lib/apiError";
import { useAuth } from "@/lib/auth";
import { formatTechLabel } from "@/lib/techCatalog";
import { titleCase } from "@/lib/utils";
import { Alert } from "@/components/ui/Alert";

/** Product defaults: Remote + last 14 days. Search allows up to 30 (index window). */
const DEFAULT_FILTERS = {
  q: "",
  workplace: "remote",
  career_stage: "",
  city: "",
  country: "",
  company: "",
  employment_type: "",
  posted_within: "14",
  skills: "",
  source: "",
  pakistan_friendly: false,
  hybrid: true,
  sort: "newest",
  page: 1,
} as const;

const parsers = {
  q: parseAsString.withDefault(DEFAULT_FILTERS.q),
  workplace: parseAsString.withDefault(DEFAULT_FILTERS.workplace),
  career_stage: parseAsString.withDefault(DEFAULT_FILTERS.career_stage),
  city: parseAsString.withDefault(DEFAULT_FILTERS.city),
  country: parseAsString.withDefault(DEFAULT_FILTERS.country),
  company: parseAsString.withDefault(DEFAULT_FILTERS.company),
  employment_type: parseAsString.withDefault(DEFAULT_FILTERS.employment_type),
  posted_within: parseAsString.withDefault(DEFAULT_FILTERS.posted_within),
  skills: parseAsString.withDefault(DEFAULT_FILTERS.skills),
  source: parseAsString.withDefault(DEFAULT_FILTERS.source),
  pakistan_friendly: parseAsBoolean.withDefault(DEFAULT_FILTERS.pakistan_friendly),
  hybrid: parseAsBoolean.withDefault(DEFAULT_FILTERS.hybrid),
  sort: parseAsString.withDefault(DEFAULT_FILTERS.sort),
  page: parseAsInteger.withDefault(DEFAULT_FILTERS.page),
};

const sortOptions = [
  { value: "newest", label: "Newest first" },
  { value: "relevance", label: "Best match" },
  { value: "company", label: "Company A–Z" },
];

function JobsSearchInner() {
  const { user } = useAuth();
  const [params, setParams] = useQueryStates(parsers, {
    history: "replace",
    shallow: true,
  });
  const [filtersOpen, setFiltersOpen] = useState(false);

  const [draft, setDraft] = useState<SearchFilterState>({
    q: params.q,
    workplace: params.workplace,
    career_stage: params.career_stage,
    city: params.city,
    country: params.country,
    company: params.company,
    employment_type: params.employment_type,
    posted_within: params.posted_within,
    skills: params.skills,
    source: params.source,
    pakistan_friendly: params.pakistan_friendly,
    hybrid: params.hybrid,
  });

  useEffect(() => {
    setDraft({
      q: params.q,
      workplace: params.workplace,
      career_stage: params.career_stage,
      city: params.city,
      country: params.country,
      company: params.company,
      employment_type: params.employment_type,
      posted_within: params.posted_within,
      skills: params.skills,
      source: params.source,
      pakistan_friendly: params.pakistan_friendly,
      hybrid: params.hybrid,
    });
  }, [params]);

  // Debounce free-text query into the URL
  useEffect(() => {
    if (draft.q === params.q) return;
    const t = window.setTimeout(() => {
      void setParams({ q: draft.q || null, page: null });
    }, 400);
    return () => window.clearTimeout(t);
  }, [draft.q, params.q, setParams]);

  const queryKey = useMemo(() => ["jobs", params] as const, [params]);

  const { data, isLoading, isFetching, error, isPlaceholderData } = useQuery({
    queryKey,
    queryFn: ({ signal }) =>
      searchJobs(
        {
          q: params.q || undefined,
          workplace: params.workplace || undefined,
          career_stage: params.career_stage || undefined,
          city: params.city || undefined,
          country: params.country || undefined,
          company: params.company || undefined,
          employment_type: params.employment_type || undefined,
          posted_within: Number(params.posted_within) || 14,
          skills: params.skills || undefined,
          source: params.source || undefined,
          pakistan_friendly: params.pakistan_friendly || undefined,
          sort: params.sort || "newest",
          page: params.page,
          page_size: 20,
          hybrid: params.hybrid,
        },
        { signal },
      ),
    placeholderData: (prev) => prev,
    staleTime: 30_000,
  });

  const applyDraft = useCallback(() => {
    void setParams({ ...draft, page: 1 });
    setFiltersOpen(false);
  }, [draft, setParams]);

  const clear = useCallback(() => {
    // Draft UI back to product defaults immediately
    setDraft({
      q: DEFAULT_FILTERS.q,
      workplace: DEFAULT_FILTERS.workplace,
      career_stage: DEFAULT_FILTERS.career_stage,
      city: DEFAULT_FILTERS.city,
      country: DEFAULT_FILTERS.country,
      company: DEFAULT_FILTERS.company,
      employment_type: DEFAULT_FILTERS.employment_type,
      posted_within: DEFAULT_FILTERS.posted_within,
      skills: DEFAULT_FILTERS.skills,
      source: DEFAULT_FILTERS.source,
      pakistan_friendly: DEFAULT_FILTERS.pakistan_friendly,
      hybrid: DEFAULT_FILTERS.hybrid,
    });
    // nuqs: null removes keys from the URL so withDefault values apply cleanly.
    // Setting "" / the default string can be a no-op when clearOnDefault is on.
    void setParams({
      q: null,
      workplace: null,
      career_stage: null,
      city: null,
      country: null,
      company: null,
      employment_type: null,
      posted_within: null,
      skills: null,
      source: null,
      pakistan_friendly: null,
      hybrid: null,
      sort: null,
      page: null,
    });
    setFiltersOpen(false);
  }, [setParams]);

  const activeChips = useMemo(() => {
    const chips: Array<{ key: string; label: string; clear: () => void }> = [];
    // Show everything that actually shapes results (including defaults) so users
    // can see and remove filters.
    if (params.q) {
      chips.push({
        key: "q",
        label: `Search: “${params.q}”`,
        clear: () => void setParams({ q: null, page: null }),
      });
    }
    chips.push({
      key: "workplace",
      label: params.workplace
        ? `Workplace: ${titleCase(params.workplace)}`
        : "Workplace: any",
      clear: () =>
        void setParams({
          workplace: params.workplace === DEFAULT_FILTERS.workplace ? "" : null,
          page: null,
        }),
    });
    const days = params.posted_within || DEFAULT_FILTERS.posted_within;
    chips.push({
      key: "days",
      label:
        days === "1"
          ? "Posted: last 24 hours"
          : `Posted: last ${days} days`,
      clear: () =>
        void setParams({
          // Reset to the product freshness window (never wider than the index).
          posted_within: null,
          page: null,
        }),
    });
    if (params.career_stage) {
      chips.push({
        key: "stage",
        label: `Experience: ${titleCase(params.career_stage)}`,
        clear: () => void setParams({ career_stage: null, page: null }),
      });
    }
    if (params.city) {
      chips.push({
        key: "city",
        label: `City: ${params.city}`,
        clear: () => void setParams({ city: null, page: null }),
      });
    }
    if (params.country) {
      chips.push({
        key: "country",
        label: `Country: ${params.country}`,
        clear: () => void setParams({ country: null, page: null }),
      });
    }
    if (params.company) {
      chips.push({
        key: "company",
        label: `Company: ${params.company}`,
        clear: () => void setParams({ company: null, page: null }),
      });
    }
    if (params.employment_type) {
      chips.push({
        key: "employment",
        label: `Employment: ${titleCase(params.employment_type)}`,
        clear: () => void setParams({ employment_type: null, page: null }),
      });
    }
    if (params.source) {
      chips.push({
        key: "source",
        label: `Source: ${params.source}`,
        clear: () => void setParams({ source: null, page: null }),
      });
    }
    if (params.pakistan_friendly) {
      chips.push({
        key: "pk",
        label: "Pakistan-friendly",
        clear: () => void setParams({ pakistan_friendly: null, page: null }),
      });
    }
    if (params.sort && params.sort !== DEFAULT_FILTERS.sort) {
      const sortLabel =
        sortOptions.find((o) => o.value === params.sort)?.label || params.sort;
      chips.push({
        key: "sort",
        label: `Sort: ${sortLabel}`,
        clear: () => void setParams({ sort: null, page: null }),
      });
    }
    const seenSkills = new Set<string>();
    for (const skill of params.skills
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 12)) {
      const lower = skill.toLowerCase();
      if (seenSkills.has(lower)) continue;
      seenSkills.add(lower);
      chips.push({
        key: `skill-${lower}`,
        label: `Tech: ${formatTechLabel(skill)}`,
        clear: () => {
          const next = params.skills
            .split(",")
            .map((s) => s.trim())
            .filter((s) => s && s.toLowerCase() !== lower)
            .join(", ");
          void setParams({ skills: next || null, page: null });
        },
      });
    }
    return chips;
  }, [params, setParams]);

  const resultsSummary = useMemo(() => {
    const bits: string[] = [];
    if (params.workplace) bits.push(titleCase(params.workplace));
    else bits.push("any workplace");
    const days = params.posted_within || DEFAULT_FILTERS.posted_within;
    bits.push(days === "1" ? "posted in the last 24 hours" : `posted in the last ${days} days`);
    if (params.city) bits.push(`city “${params.city}”`);
    if (params.country) bits.push(`country “${params.country}”`);
    if (params.company) bits.push(`company “${params.company}”`);
    if (params.career_stage) bits.push(`${titleCase(params.career_stage)} level`);
    if (params.employment_type) bits.push(titleCase(params.employment_type));
    if (params.source) bits.push(`source ${params.source}`);
    if (params.pakistan_friendly) bits.push("Pakistan-friendly remote");
    const tech = params.skills
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 6)
      .map(formatTechLabel);
    if (tech.length) bits.push(`technologies: ${tech.join(", ")}`);
    if (params.q) bits.push(`matching “${params.q}”`);
    const sortLabel =
      sortOptions.find((o) => o.value === params.sort)?.label || "newest first";
    bits.push(`sorted by ${sortLabel.toLowerCase()}`);
    return bits.join(" · ");
  }, [params]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const profile = user?.profile;
  const hasCustomFilters =
    Boolean(params.q) ||
    Boolean(params.city) ||
    Boolean(params.country) ||
    Boolean(params.company) ||
    Boolean(params.career_stage) ||
    Boolean(params.employment_type) ||
    Boolean(params.source) ||
    Boolean(params.skills) ||
    params.pakistan_friendly ||
    (params.workplace && params.workplace !== DEFAULT_FILTERS.workplace) ||
    (params.posted_within && params.posted_within !== DEFAULT_FILTERS.posted_within) ||
    (params.sort && params.sort !== DEFAULT_FILTERS.sort) ||
    params.workplace === "";

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <div className="mb-6 sm:mb-8">
        <h1 className="font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          Jobs
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted sm:text-base">
          Verified roles with official apply links. Default view is remote jobs from the last 14
          days — add filters only when you want them.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 lg:hidden">
        <Button
          variant="secondary"
          size="sm"
          type="button"
          aria-expanded={filtersOpen}
          onClick={() => setFiltersOpen((o) => !o)}
        >
          <SlidersHorizontal className="h-4 w-4" aria-hidden />
          {filtersOpen ? "Hide filters" : "Filters"}
          {hasCustomFilters ? (
            <span className="rounded bg-accent-soft px-1.5 text-[10px] font-semibold text-accent">
              on
            </span>
          ) : null}
        </Button>
        <label className="inline-flex items-center gap-2 rounded-md border border-line bg-elevated px-2 py-1.5 text-sm">
          <ArrowUpDown className="h-3.5 w-3.5 text-muted" aria-hidden />
          <span className="sr-only">Sort</span>
          <select
            value={params.sort}
            onChange={(e) => void setParams({ sort: e.target.value, page: 1 })}
            className="bg-transparent text-sm text-ink outline-none"
            aria-label="Sort jobs"
          >
            {sortOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,300px)_1fr] xl:grid-cols-[minmax(0,320px)_1fr] lg:gap-8">
        <aside
          className={`h-fit max-h-[min(100%,calc(100vh-6rem))] overflow-y-auto overscroll-contain rounded-xl border border-line bg-elevated p-4 shadow-soft atlas-scroll sm:p-5 lg:sticky lg:top-24 lg:block ${
            filtersOpen ? "block" : "hidden"
          }`}
        >
          <SearchFilters
            value={draft}
            onChange={setDraft}
            onSubmit={applyDraft}
            onClear={clear}
            profileSkills={profile?.skills}
            profileTechnologies={profile?.technologies}
          />
        </aside>

        <section className="min-w-0">
          <div className="mb-4 rounded-xl border border-line bg-elevated p-4 shadow-soft sm:p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink" role="status" aria-live="polite">
                  {isLoading && !data
                    ? "Searching catalogue…"
                    : data
                      ? `Showing ${data.total.toLocaleString()} ${
                          data.total === 1 ? "job" : "jobs"
                        }`
                      : "Results"}
                  {isFetching || isPlaceholderData ? (
                    <span className="font-normal text-muted"> · updating</span>
                  ) : null}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-muted">{resultsSummary}</p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2">
                {user ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    type="button"
                    href={`/alerts?q=${encodeURIComponent(params.q || "")}&skills=${encodeURIComponent(params.skills || "")}`}
                  >
                    Save as Pulse
                  </Button>
                ) : null}
                <label className="hidden items-center gap-2 rounded-md border border-line bg-paper px-3 py-2 text-sm lg:inline-flex">
                  <ArrowUpDown className="h-3.5 w-3.5 text-muted" aria-hidden />
                  <span className="text-muted">Sort</span>
                  <select
                    value={params.sort}
                    onChange={(e) => void setParams({ sort: e.target.value, page: 1 })}
                    className="bg-transparent font-medium text-ink outline-none"
                    aria-label="Sort jobs"
                  >
                    {sortOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>

            <div className="mt-3 border-t border-line pt-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted">
                  Active filters
                </p>
                <button
                  type="button"
                  onClick={clear}
                  className="text-xs font-medium text-accent hover:underline"
                >
                  Reset to remote · 14 days
                </button>
              </div>
              <ul className="flex flex-wrap gap-1.5" aria-label="Active filters">
                {activeChips.map((chip) => (
                  <li key={chip.key}>
                    <button
                      type="button"
                      onClick={chip.clear}
                      className="inline-flex items-center gap-1 rounded-md border border-line bg-paper px-2 py-1 text-xs font-medium text-ink transition hover:border-accent/40 hover:bg-accent-soft/40"
                    >
                      {chip.label}
                      <X className="h-3 w-3 text-muted" aria-hidden />
                      <span className="sr-only">Remove {chip.label}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {error ? (
            <Alert tone="error" title="Search unavailable" className="mb-4">
              {formatApiError(error, "Search failed. Is the API running on port 8000?")}
            </Alert>
          ) : null}

          {isLoading && !data ? (
            <div className="space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <JobCardSkeleton key={i} />
              ))}
            </div>
          ) : null}

          {!isLoading && data && data.results.length === 0 ? (
            <div className="rounded-xl border border-dashed border-line bg-elevated p-8 text-center sm:p-10">
              <h2 className="font-display text-xl font-semibold text-ink">No matching roles</h2>
              <p className="mx-auto mt-2 max-w-md text-sm text-muted">
                Nothing in the catalogue fits {resultsSummary.toLowerCase()}. Try removing a
                technology chip, clearing city/country, or widening the date window.
              </p>
              <Button className="mt-5" variant="secondary" onClick={clear}>
                Reset filters
              </Button>
            </div>
          ) : null}

          <div
            className={`space-y-3 sm:space-y-4 ${isFetching && data ? "opacity-80 transition-opacity" : ""}`}
          >
            {data?.results.map((job, i) => (
              <JobCard key={job.id} job={job} index={i} />
            ))}
          </div>

          {data && data.total > data.page_size ? (
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                disabled={params.page <= 1}
                onClick={() => void setParams({ page: Math.max(1, params.page - 1) })}
              >
                Previous
              </Button>
              <span className="text-sm text-muted">
                Page {params.page} of {totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={params.page >= totalPages}
                onClick={() => void setParams({ page: params.page + 1 })}
              >
                Next
              </Button>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

export default function JobsPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl px-4 py-10">
          <JobCardSkeleton />
        </div>
      }
    >
      <JobsSearchInner />
    </Suspense>
  );
}
