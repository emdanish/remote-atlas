import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SeoLandingShell } from "@/components/seo/SeoLandingShell";
import { getSeoSkill, getSeoSkills, searchJobs, SITE_URL } from "@/lib/api";
import { skillTagsForSlug } from "@/lib/seoTaxonomy";
import { buildBreadcrumbJsonLd, safeJsonLd } from "@/lib/seo";

export const revalidate = 1800;

type Props = {
  params: Promise<{ skill: string }>;
  searchParams: Promise<{ page?: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { skill } = await params;
  const meta = await getSeoSkill(skill).catch(() => null);
  if (!meta) {
    return { title: "Skill not found", robots: { index: false, follow: true } };
  }
  const path = `/remote-${skill}-jobs`;
  const title = `${meta.label} remote jobs`;
  const description = `Browse ${meta.count.toLocaleString()} fresh remote ${meta.label} jobs from company career systems and trusted feeds. Search with intent and apply on the employer’s official page.`;
  return {
    title,
    description,
    alternates: { canonical: path },
    robots: { index: true, follow: true },
    openGraph: {
      title: `${title} | Remote Atlas`,
      description,
      url: `${SITE_URL}${path}`,
      siteName: "Remote Atlas",
      type: "website",
    },
  };
}

export default async function SkillSeoPage({ params, searchParams }: Props) {
  const { skill } = await params;
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page) || 1);
  const pageSize = 20;

  const meta = await getSeoSkill(skill).catch(() => null);
  if (!meta) notFound();

  const tags = skillTagsForSlug(skill);
  const [results, relatedSkills] = await Promise.all([
    searchJobs({
      skills: tags,
      workplace: "remote",
      page,
      page_size: pageSize,
      sort: "newest",
      hybrid: false,
    }),
    getSeoSkills(12).catch(() => []),
  ]);

  const path = `/remote-${skill}-jobs`;
  const breadcrumb = [
    { name: "Home", path: "/" },
    { name: "Jobs", path: "/jobs" },
    { name: `${meta.label} remote`, path },
  ];
  const related = relatedSkills.filter((s) => s.slug !== skill).slice(0, 8);
  const ld = buildBreadcrumbJsonLd(breadcrumb);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: safeJsonLd(ld) }}
      />
      <SeoLandingShell
        h1={`${meta.label} remote jobs`}
        intro={`Fresh remote ${meta.label} roles indexed from authentic ATS boards and public tech feeds. Listings outside the freshness window leave the active index automatically.`}
        jobCount={meta.count}
        freshnessDays={results.freshness_days}
        breadcrumb={breadcrumb}
        jobs={results.results}
        page={page}
        pageSize={pageSize}
        total={results.total}
        basePath={path}
        related={related}
        relatedTitle="Related skills"
      />
    </>
  );
}
