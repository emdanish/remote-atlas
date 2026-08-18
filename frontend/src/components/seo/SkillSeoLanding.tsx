/**
 * Shared skill SEO landing renderer.
 * Used by both the public rewrite target and any internal /seo/skills/* access.
 */
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SeoLandingShell } from "@/components/seo/SeoLandingShell";
import { getSeoSkill, getSeoSkills, searchJobs, SITE_URL } from "@/lib/api";
import { skillTagsForSlug } from "@/lib/seoTaxonomy";

export const revalidate = 1800;

type Props = {
  skill: string;
  page: number;
};

export async function skillSeoMetadata(skill: string): Promise<Metadata> {
  const meta = await getSeoSkill(skill).catch(() => null);
  if (!meta || meta.count < 1) notFound();
  const path = `/remote-${skill}-jobs`;
  const title = `Remote ${meta.label} Jobs`;
  const description = `Find ${meta.count.toLocaleString()} fresh remote ${meta.label} jobs from company career systems and trusted feeds. Browse current openings and apply on the employer's official site.`;
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

export async function SkillSeoLanding({ skill, page }: Props) {
  const pageSize = 20;
  const meta = await getSeoSkill(skill).catch(() => null);
  if (!meta || meta.count < 1) notFound();

  const tags = skillTagsForSlug(skill);
  const [results, relatedSkills] = await Promise.all([
    searchJobs({
      skills: tags,
      // Skill landings are remote-first; counts use the same workplace filter.
      workplace: "remote",
      page,
      page_size: pageSize,
      sort: "newest",
      hybrid: false,
    }),
    getSeoSkills(12).catch(() => []),
  ]);

  if (page === 1 && results.total === 0) notFound();

  const path = `/remote-${skill}-jobs`;
  const breadcrumb = [
    { name: "Home", path: "/" },
    { name: "Jobs", path: "/jobs" },
    { name: `Remote ${meta.label} Jobs`, path },
  ];
  const related = relatedSkills.filter((s) => s.slug !== skill).slice(0, 8);

  return (
    <SeoLandingShell
        h1={`Remote ${meta.label} Jobs`}
        intro={`Fresh remote ${meta.label} roles from authentic ATS boards and public tech feeds. Apply on the employer's official career page — listings outside the freshness window leave the active index automatically.`}
        jobCount={results.total || meta.count}
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
  );
}
