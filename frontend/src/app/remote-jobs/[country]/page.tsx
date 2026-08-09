import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SeoLandingShell } from "@/components/seo/SeoLandingShell";
import { getSeoLocation, getSeoLocations, getSeoSkills, searchJobs, SITE_URL } from "@/lib/api";
import { buildBreadcrumbJsonLd, safeJsonLd } from "@/lib/seo";

export const revalidate = 1800;

type Props = {
  params: Promise<{ country: string }>;
  searchParams: Promise<{ page?: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { country } = await params;
  const meta = await getSeoLocation(country, "country").catch(() => null);
  if (!meta) {
    return { title: "Location not found", robots: { index: false, follow: true } };
  }
  const path = `/remote-jobs/${country}`;
  const title =
    country === "worldwide"
      ? "Worldwide remote jobs"
      : `Remote jobs · ${meta.label}`;
  const description = `Browse ${meta.count.toLocaleString()} fresh roles tied to ${meta.label} in the Remote Atlas index. Location signals come from source listings; apply on official pages.`;
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: {
      title: `${title} | Remote Atlas`,
      description,
      url: `${SITE_URL}${path}`,
      siteName: "Remote Atlas",
    },
  };
}

export default async function CountrySeoPage({ params, searchParams }: Props) {
  const { country } = await params;
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page) || 1);
  const pageSize = 20;
  const meta = await getSeoLocation(country, "country").catch(() => null);
  if (!meta) notFound();

  const searchParamsJob =
    country === "pakistan"
      ? {
          pakistan_friendly: true as const,
          workplace: "remote" as const,
          page,
          page_size: pageSize,
          sort: "newest" as const,
          hybrid: false as const,
        }
      : country === "worldwide"
        ? {
            workplace: "remote" as const,
            page,
            page_size: pageSize,
            sort: "newest" as const,
            hybrid: false as const,
            q: "worldwide OR anywhere OR global",
          }
        : {
            country: meta.label,
            workplace: "remote" as const,
            page,
            page_size: pageSize,
            sort: "newest" as const,
            hybrid: false as const,
          };

  const [results, skills, locations] = await Promise.all([
    searchJobs(searchParamsJob),
    getSeoSkills(8).catch(() => []),
    getSeoLocations("country").catch(() => []),
  ]);

  const path = `/remote-jobs/${country}`;
  const breadcrumb = [
    { name: "Home", path: "/" },
    { name: "Remote jobs", path: "/jobs?workplace=remote" },
    { name: meta.label, path },
  ];
  const ld = buildBreadcrumbJsonLd(breadcrumb);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(ld) }} />
      <SeoLandingShell
        h1={
          country === "worldwide"
            ? "Worldwide remote jobs"
            : `Remote jobs · ${meta.label}`
        }
        intro={
          country === "pakistan"
            ? "Remote roles flagged as Pakistan-friendly or tied to Pakistan locations in source data. Always confirm eligibility on the employer’s page."
            : `Jobs whose source location text or workplace signals relate to ${meta.label}. Semantics follow source data — we do not invent locations.`
        }
        jobCount={meta.count}
        freshnessDays={results.freshness_days}
        breadcrumb={breadcrumb}
        jobs={results.results}
        page={page}
        pageSize={pageSize}
        total={results.total}
        basePath={path}
        related={[
          ...skills.slice(0, 5),
          ...locations.filter((l) => l.slug !== country).slice(0, 4),
        ]}
        relatedTitle="Related exploration"
      />
    </>
  );
}
