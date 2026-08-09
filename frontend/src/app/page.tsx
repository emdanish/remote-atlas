import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  FileText,
  MapPin,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Reveal } from "@/components/marketing/Reveal";
import { StatCounter } from "@/components/marketing/StatCounter";
import { getIngestStats, getSeoLocations, getSeoSkills } from "@/lib/api";
import { safeJsonLd } from "@/lib/seo";

export const metadata: Metadata = {
  title: {
    absolute: "Remote Atlas | Candidate-first job discovery",
  },
  description:
    "A job search engine for candidates: fresh tech roles from official career systems, intent-aware search, and optional resume tailoring. Apply on the employer’s page.",
  alternates: { canonical: "/" },
  openGraph: {
    title: "Remote Atlas | Candidate-first job discovery",
    description:
      "Fresh roles from trusted sources. Search what you want. Apply on the official career page.",
    url: "/",
  },
};

export default async function LandingPage() {
  let stats: {
    active: number;
    companies: number;
    sources: number;
    freshness: number;
    lastSourceRun: string | null;
  } | null = null;
  try {
    const data = await getIngestStats();
    const lastSourceRun =
      data.sources
        .map((s) => s.last_run)
        .filter((v): v is string => Boolean(v))
        .sort()
        .at(-1) ?? null;
    stats = {
      active: data.inventory.fresh_jobs || data.inventory.active_jobs,
      companies: data.inventory.indexed_companies,
      sources: data.inventory.active_sources,
      freshness: data.freshness_days,
      lastSourceRun,
    };
  } catch {
    // Marketing page stays usable if the API is briefly offline.
  }

  const updatedLabel = formatIndexAge(stats?.lastSourceRun ?? null);

  const freshness = stats?.freshness ?? 14;
  const faqItems = [
    {
      q: "Where do the jobs come from?",
      a: "Public applicant tracking systems and reputable public feeds. We index them; we do not invent listings.",
    },
    {
      q: "How fresh is the index?",
      a: `Active roles must fall within the ${freshness}-day freshness window. Re-seeing a listing does not make an old posting “new.”`,
    },
    {
      q: "Is Remote Atlas free to search?",
      a: "Yes. Create an account when you want saves, matches, alerts, and resume tailoring history.",
    },
    {
      q: "Does tailoring change my original file?",
      a: "No. Your uploaded original remains stored. Tailored PDFs are generated as separate artifacts.",
    },
  ];

  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqItems.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.a,
      },
    })),
  };

  let explore: { skills: { href: string; label: string; count: number }[]; locations: { href: string; label: string; count: number }[] } =
    { skills: [], locations: [] };
  try {
    const [skills, countries] = await Promise.all([
      getSeoSkills(8),
      getSeoLocations("country"),
    ]);
    explore = {
      skills: skills.slice(0, 8),
      locations: countries.slice(0, 6),
    };
  } catch {
    /* optional hub */
  }

  return (
    <div>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: safeJsonLd(faqJsonLd) }}
      />
      {/* Hero — brand first, one composition */}
      <section className="relative overflow-hidden border-b border-line bg-ink text-white">
        <div className="absolute inset-0 atlas-dark-grid opacity-60" aria-hidden />
        <div
          className="absolute -right-24 top-0 h-[520px] w-[520px] rounded-full bg-accent/20 blur-3xl"
          aria-hidden
        />
        <div className="absolute -left-20 bottom-0 h-72 w-72 rounded-full bg-white/5 blur-3xl" aria-hidden />

        <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-16 sm:px-6 sm:pb-20 sm:pt-20 lg:pb-24 lg:pt-24">
          <p className="font-display text-sm font-semibold tracking-[0.28em] text-teal-300/90 sm:text-base">
            REMOTE ATLAS
          </p>
          <h1 className="mt-5 max-w-3xl font-display text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-balance sm:text-5xl lg:text-6xl">
            A job search engine built for candidates.
          </h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-white/70 sm:text-lg sm:leading-8">
            Fresh roles from company career systems and trusted sources. Search what
            you actually want. Apply on the employer&apos;s official page. Optionally
            tailor your resume to the role.
          </p>

          <form action="/jobs" className="mt-10 max-w-2xl">
            <label htmlFor="hero-q" className="sr-only">
              Search jobs
            </label>
            <div className="flex flex-col gap-2 rounded-xl border border-white/15 bg-white/5 p-2 backdrop-blur-sm sm:flex-row sm:items-center">
              <div className="flex min-w-0 flex-1 items-center gap-3 px-3">
                <Search className="h-5 w-5 shrink-0 text-teal-300" aria-hidden />
                <input
                  id="hero-q"
                  name="q"
                  placeholder="Role, stack, or company — e.g. TypeScript remote"
                  className="h-11 min-w-0 flex-1 border-0 bg-transparent text-white outline-none placeholder:text-white/40"
                />
              </div>
              <Button type="submit" size="lg" className="shrink-0 bg-teal-300 text-ink hover:bg-teal-200">
                Search the index
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Button>
            </div>
          </form>

          <p className="mt-5 text-sm text-white/50">
            No account required to search. Listings older than{" "}
            {stats?.freshness ?? 14} days leave the active index automatically.
          </p>
        </div>
      </section>

      {/* Live index — product feature, not decoration */}
      <section className="border-b border-line bg-elevated" aria-labelledby="live-index-heading">
        <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-14">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-bold tracking-[0.18em] text-accent">LIVE INDEX</p>
              <h2 id="live-index-heading" className="mt-2 font-display text-2xl font-semibold text-ink sm:text-3xl">
                What&apos;s currently searchable
              </h2>
            </div>
            <p className="text-sm text-muted">
              {stats
                ? updatedLabel
                  ? `Index signal last refreshed ${updatedLabel}`
                  : "Counts come from the live database"
                : "Connect the API to see live counts"}
            </p>
          </div>
          <div className="mt-10 grid grid-cols-2 gap-8 md:grid-cols-4">
            <StatCounter value={stats?.active ?? null} label="Active opportunities" />
            <StatCounter value={stats?.companies ?? null} label="Companies" />
            <StatCounter value={stats?.sources ?? null} label="Trusted sources" />
            <StatCounter
              value={stats?.freshness ?? null}
              label="Day freshness window"
              suffix={stats ? "d" : ""}
            />
          </div>
        </div>
      </section>

      {(explore.skills.length > 0 || explore.locations.length > 0) && (
        <section className="border-b border-line bg-paper" aria-labelledby="explore-heading">
          <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-14">
            <p className="text-xs font-bold tracking-[0.18em] text-accent">EXPLORE</p>
            <h2 id="explore-heading" className="mt-2 font-display text-2xl font-semibold text-ink">
              Popular remote paths
            </h2>
            <p className="mt-2 max-w-xl text-sm text-muted">
              Curated landings with enough fresh inventory to be useful — not every filter
              combination.
            </p>
            {explore.skills.length ? (
              <div className="mt-8">
                <h3 className="text-sm font-semibold text-ink">By skill</h3>
                <ul className="mt-3 flex flex-wrap gap-2">
                  {explore.skills.map((s) => (
                    <li key={s.href}>
                      <Link
                        href={s.href}
                        className="inline-flex rounded-md border border-line bg-elevated px-3 py-1.5 text-sm font-medium text-ink hover:border-accent hover:text-accent"
                      >
                        {s.label}
                        <span className="ml-1.5 text-muted">({s.count})</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {explore.locations.length ? (
              <div className="mt-8">
                <h3 className="text-sm font-semibold text-ink">By location signal</h3>
                <ul className="mt-3 flex flex-wrap gap-2">
                  {explore.locations.map((s) => (
                    <li key={s.href}>
                      <Link
                        href={s.href}
                        className="inline-flex rounded-md border border-line bg-elevated px-3 py-1.5 text-sm font-medium text-ink hover:border-accent hover:text-accent"
                      >
                        {s.label}
                        <span className="ml-1.5 text-muted">({s.count})</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            <p className="mt-6">
              <Link href="/companies" className="text-sm font-semibold text-accent hover:underline">
                Browse companies →
              </Link>
            </p>
          </div>
        </section>
      )}

      {/* Product promise */}
      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-24">
        <Reveal>
          <div className="max-w-2xl">
            <p className="text-xs font-bold tracking-[0.18em] text-accent">WHY IT EXISTS</p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
              Not a recruiter marketplace. Not a feed of paid promotions.
            </h2>
            <p className="mt-5 text-base leading-8 text-muted sm:text-lg">
              Remote Atlas discovers listings from authentic company ATS systems and
              curated feeds, normalizes them, enforces freshness, and gives you filters
              that describe real decisions — remote, hybrid, stack, stage, where you can apply.
            </p>
          </div>
        </Reveal>

        <div className="mt-14 grid gap-10 md:grid-cols-3">
          {[
            {
              icon: ShieldCheck,
              title: "Provenance you can check",
              body: "Every role carries its source. You leave Remote Atlas on the employer’s own application page — we never insert ourselves as a portal.",
            },
            {
              icon: Search,
              title: "Search for intent",
              body: "Hybrid search combines keywords with semantic relevance when embeddings are available. Traditional search still works if AI is offline.",
            },
            {
              icon: FileText,
              title: "Resume tailoring for a real job",
              body: "Pick a listing, upload your resume, and generate a role-aligned version without inventing experience. Your original stays the source of truth.",
            },
          ].map((item, i) => (
            <Reveal key={item.title} delay={i * 0.05}>
              <article className="border-t border-line pt-6">
                <item.icon className="h-5 w-5 text-accent" aria-hidden />
                <h3 className="mt-4 text-lg font-bold text-ink">{item.title}</h3>
                <p className="mt-2 text-sm leading-7 text-muted">{item.body}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-y border-line bg-elevated">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-24">
          <Reveal>
            <p className="text-xs font-bold tracking-[0.18em] text-accent">HOW IT WORKS</p>
            <h2 className="mt-3 max-w-xl font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
              From discovery to the application page.
            </h2>
          </Reveal>
          <ol className="mt-12 grid gap-8 md:grid-cols-4">
            {[
              {
                n: "1",
                title: "Search",
                body: "Describe the role or stack. Filters narrow workplace, stage, location, and recency.",
              },
              {
                n: "2",
                title: "Evaluate",
                body: "Read the listing with source, skills, and company context — no paywalled “unlock”.",
              },
              {
                n: "3",
                title: "Tailor (optional)",
                body: "Generate a focused resume for that specific job while preserving your facts.",
              },
              {
                n: "4",
                title: "Apply directly",
                body: "Continue on the official career site. Track what you save in your workspace.",
              },
            ].map((step, i) => (
              <Reveal key={step.n} delay={i * 0.04}>
                <li>
                  <span className="font-display text-3xl font-semibold text-accent/35">{step.n}</span>
                  <h3 className="mt-3 text-base font-bold text-ink">{step.title}</h3>
                  <p className="mt-2 text-sm leading-7 text-muted">{step.body}</p>
                </li>
              </Reveal>
            ))}
          </ol>
        </div>
      </section>

      {/* Resume tailoring callout */}
      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-24">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <Reveal>
            <p className="text-xs font-bold tracking-[0.18em] text-accent">RESUME TAILORING</p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
              Align your resume to one opportunity — without fabricating a new one.
            </h2>
            <p className="mt-5 text-base leading-8 text-muted">
              Open any job, upload a PDF or DOCX, and Remote Atlas rewrites emphasis and
              wording for that role. Contact details, references, employers, and projects
              are preserved from your original. Failed or incomplete AI output never
              replaces your resume with a blank document.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button href="/jobs" size="lg">
                Find a role to tailor for
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Button>
              <Button href="/register" variant="secondary" size="lg">
                Create a free account
              </Button>
            </div>
          </Reveal>

          <Reveal delay={0.06}>
            <div className="rounded-2xl border border-line bg-elevated p-6 shadow-soft sm:p-8">
              <div className="flex items-start justify-between gap-4 border-b border-line pb-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                    Example path
                  </p>
                  <p className="mt-1 font-display text-xl font-semibold text-ink">
                    Job detail → Tailor resume
                  </p>
                </div>
                <Sparkles className="h-5 w-5 text-accent" aria-hidden />
              </div>
              <ul className="mt-5 space-y-4 text-sm leading-6 text-muted">
                <li className="flex gap-3">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                  Uses only evidence already in your uploaded resume.
                </li>
                <li className="flex gap-3">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                  Keeps structure and major sections — summary, experience, projects, education.
                </li>
                <li className="flex gap-3">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                  Exports an ATS-safe PDF you can download and apply with.
                </li>
              </ul>
              <div className="mt-6 rounded-xl border border-line bg-paper p-4">
                <p className="flex items-center gap-2 text-xs font-semibold text-ink">
                  <MapPin className="h-3.5 w-3.5 text-accent" aria-hidden />
                  Apply stays on the employer site
                </p>
                <p className="mt-1 text-xs leading-5 text-muted">
                  Tailoring improves your materials. It never rewrites the employer&apos;s application process.
                </p>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* FAQ */}
      <section className="border-t border-line bg-elevated">
        <div className="mx-auto grid max-w-6xl gap-12 px-4 py-20 sm:px-6 sm:py-24 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <p className="text-xs font-bold tracking-[0.18em] text-accent">FAQ</p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-ink">
              Short answers.
            </h2>
          </div>
          <div className="space-y-3">
            {faqItems.map((item) => (
              <details
                key={item.q}
                className="group rounded-xl border border-line bg-paper px-5 py-4 open:bg-elevated open:shadow-soft"
              >
                <summary className="cursor-pointer list-none font-semibold text-ink [&::-webkit-details-marker]:hidden">
                  <span className="flex items-center justify-between gap-4">
                    {item.q}
                    <span className="text-xl font-light text-accent transition group-open:rotate-45" aria-hidden>
                      +
                    </span>
                  </span>
                </summary>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-muted">{item.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="bg-ink text-white">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-8 px-4 py-14 sm:px-6 md:flex-row md:items-center">
          <div>
            <p className="font-display text-2xl font-semibold sm:text-3xl">
              Start with the live index.
            </p>
            <p className="mt-2 max-w-lg text-sm leading-6 text-white/65">
              Search freely. When a role matters, apply on the official page — and tailor your resume if you need the edge.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/jobs"
              className="inline-flex h-11 items-center gap-2 rounded-lg bg-teal-300 px-5 text-sm font-bold text-ink transition hover:bg-teal-200"
            >
              Browse jobs
              <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
            <Link
              href="/register"
              className="inline-flex h-11 items-center rounded-lg border border-white/25 px-5 text-sm font-bold text-white transition hover:bg-white/10"
            >
              Create account
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function formatIndexAge(iso: string | null): string | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const hours = Math.max(0, Math.round((Date.now() - then) / 3_600_000));
  if (hours < 1) return "within the last hour";
  if (hours < 48) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}
