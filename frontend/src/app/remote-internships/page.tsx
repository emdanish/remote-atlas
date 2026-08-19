import type { Metadata } from "next";
import { SeoLandingShell } from "@/components/seo/SeoLandingShell";
import { searchJobs } from "@/lib/api";

export const revalidate = 1800;

const PATH = "/remote-internships";

type Props = { searchParams: Promise<{ page?: string }> };

export const metadata: Metadata = {
  title: "Remote internships",
  description:
    "Remote software internships from company career pages and trusted public feeds. Apply on the employer’s official site — we never submit for you.",
  alternates: { canonical: PATH },
  robots: { index: true, follow: true },
  openGraph: {
    title: "Remote internships | Remote Atlas",
    description: "Fresh remote internships in tech. Official apply links only.",
    url: PATH,
    siteName: "Remote Atlas",
  },
};

export default async function RemoteInternshipsPage({ searchParams }: Props) {
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page) || 1);
  const pageSize = 20;
  const results = await searchJobs({
    workplace: "remote",
    career_stage: "internship",
    page,
    page_size: pageSize,
    sort: "newest",
    hybrid: false,
  });
  const breadcrumb = [
    { name: "Home", path: "/" },
    { name: "Jobs", path: "/jobs" },
    { name: "Internships", path: PATH },
  ];
  return (
    <SeoLandingShell
        h1="Remote internships"
        intro="Software internships from official ATS boards and public feeds. Confirm pay, dates, and work authorization on the employer page. We never submit applications for you."
        jobCount={results.total}
        freshnessDays={results.freshness_days}
        breadcrumb={breadcrumb}
        jobs={results.results}
        page={page}
        pageSize={pageSize}
        total={results.total}
        basePath={PATH}
      />
  );
}
