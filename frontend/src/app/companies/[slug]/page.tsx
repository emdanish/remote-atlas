import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SeoLandingShell } from "@/components/seo/SeoLandingShell";
import {
  getSeoCompanies,
  getSeoCompany,
  getSeoSkills,
  searchJobs,
  SITE_URL,
} from "@/lib/api";
import { buildBreadcrumbJsonLd, safeJsonLd } from "@/lib/seo";

export const revalidate = 1800;

type Props = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ page?: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const meta = await getSeoCompany(slug).catch(() => null);
  if (!meta) {
    return { title: "Company not found", robots: { index: false, follow: true } };
  }
  const path = `/companies/${slug}`;
  const title = `Remote jobs at ${meta.label}`;
  const description = `Browse ${meta.count.toLocaleString()} fresh roles at ${meta.label} on Remote Atlas. Open official career pages when you apply.`;
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

export default async function CompanySeoPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page) || 1);
  const pageSize = 20;
  const meta = await getSeoCompany(slug).catch(() => null);
  if (!meta) notFound();

  const [results, skills, companies] = await Promise.all([
    searchJobs({
      company: meta.label,
      page,
      page_size: pageSize,
      sort: "newest",
      hybrid: false,
    }),
    getSeoSkills(8).catch(() => []),
    getSeoCompanies(8).catch(() => []),
  ]);

  const path = `/companies/${slug}`;
  const breadcrumb = [
    { name: "Home", path: "/" },
    { name: "Companies", path: "/companies" },
    { name: meta.label, path },
  ];
  const ld = buildBreadcrumbJsonLd(breadcrumb);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(ld) }} />
      <SeoLandingShell
        h1={`Jobs at ${meta.label}`}
        intro={`Active roles associated with ${meta.label} in the Remote Atlas freshness window. Apply only through official employer links.`}
        jobCount={meta.count}
        freshnessDays={results.freshness_days}
        breadcrumb={breadcrumb}
        jobs={results.results}
        page={page}
        pageSize={pageSize}
        total={results.total}
        basePath={path}
        related={[...skills.slice(0, 4), ...companies.filter((c) => c.slug !== slug).slice(0, 4)]}
        relatedTitle="Explore more"
      />
    </>
  );
}
