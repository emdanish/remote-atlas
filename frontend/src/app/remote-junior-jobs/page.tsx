import type { Metadata } from "next";
import { SeoLandingShell } from "@/components/seo/SeoLandingShell";
import { searchJobs } from "@/lib/api";

export const revalidate = 1800;

const PATH = "/remote-junior-jobs";

type Props = { searchParams: Promise<{ page?: string }> };

export const metadata: Metadata = {
  title: "Remote junior and entry-level jobs",
  description:
    "Junior-eligible remote tech roles: internships, new-grad, junior titles, and unspecified IC jobs that do not ask for 3+ years. Apply on the employer’s official page.",
  alternates: { canonical: PATH },
  robots: { index: true, follow: true },
  openGraph: {
    title: "Remote junior and entry-level jobs | Remote Atlas",
    description:
      "Entry-level and intern remote tech roles from company ATS boards. We never relabel senior IC jobs as junior.",
    url: PATH,
    siteName: "Remote Atlas",
  },
};

export default async function RemoteJuniorJobsPage({ searchParams }: Props) {
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page) || 1);
  const pageSize = 20;
  const results = await searchJobs({
    workplace: "remote",
    career_stage: "junior",
    page,
    page_size: pageSize,
    sort: "newest",
    hybrid: false,
  });
  const breadcrumb = [
    { name: "Home", path: "/" },
    { name: "Jobs", path: "/jobs" },
    { name: "Junior-eligible", path: PATH },
  ];
  return (
    <SeoLandingShell
        h1="Remote junior-eligible jobs"
        intro="Internships, new-grad, junior titles, and unspecified IC roles that are not senior-coded and do not require 3+ years. Unlabeled roles show as “Seniority not stated.” Remote junior supply is scarce — this list is the honest subset, not a padded catalogue."
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
