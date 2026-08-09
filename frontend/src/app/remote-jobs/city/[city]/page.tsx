import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SeoLandingShell } from "@/components/seo/SeoLandingShell";
import { getSeoLocation, getSeoLocations, getSeoSkills, searchJobs, SITE_URL } from "@/lib/api";
import { buildBreadcrumbJsonLd, safeJsonLd } from "@/lib/seo";

export const revalidate = 1800;

type Props = {
  params: Promise<{ city: string }>;
  searchParams: Promise<{ page?: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { city } = await params;
  const meta = await getSeoLocation(city, "city").catch(() => null);
  if (!meta) {
    return { title: "City not found", robots: { index: false, follow: true } };
  }
  const path = `/remote-jobs/city/${city}`;
  const title = `Jobs mentioning ${meta.label}`;
  const description = `Browse ${meta.count.toLocaleString()} fresh roles that mention ${meta.label} in source location data on Remote Atlas.`;
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

export default async function CitySeoPage({ params, searchParams }: Props) {
  const { city } = await params;
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page) || 1);
  const pageSize = 20;
  const meta = await getSeoLocation(city, "city").catch(() => null);
  if (!meta) notFound();

  const [results, skills, cities] = await Promise.all([
    searchJobs({
      city: meta.label,
      page,
      page_size: pageSize,
      sort: "newest",
      hybrid: false,
    }),
    getSeoSkills(8).catch(() => []),
    getSeoLocations("city").catch(() => []),
  ]);

  const path = `/remote-jobs/city/${city}`;
  const breadcrumb = [
    { name: "Home", path: "/" },
    { name: "Jobs", path: "/jobs" },
    { name: meta.label, path },
  ];
  const ld = buildBreadcrumbJsonLd(breadcrumb);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(ld) }} />
      <SeoLandingShell
        h1={`Jobs mentioning ${meta.label}`}
        intro={`${meta.label} appears in source location text for these fresh listings. Remote roles may still hire from many regions — check the employer page.`}
        jobCount={meta.count}
        freshnessDays={results.freshness_days}
        breadcrumb={breadcrumb}
        jobs={results.results}
        page={page}
        pageSize={pageSize}
        total={results.total}
        basePath={path}
        related={[
          ...skills.slice(0, 4),
          ...cities.filter((c) => c.slug !== city).slice(0, 4),
        ]}
        relatedTitle="Related"
      />
    </>
  );
}
