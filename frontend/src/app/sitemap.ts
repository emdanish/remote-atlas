import type { MetadataRoute } from "next";
import { searchJobs, SITE_URL } from "@/lib/api";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticRoutes: MetadataRoute.Sitemap = [
    { url: SITE_URL, lastModified: new Date(), changeFrequency: "daily", priority: 1 },
    {
      url: `${SITE_URL}/jobs`,
      lastModified: new Date(),
      changeFrequency: "hourly",
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/login`,
      changeFrequency: "monthly",
      priority: 0.3,
    },
    {
      url: `${SITE_URL}/register`,
      changeFrequency: "monthly",
      priority: 0.4,
    },
  ];

  try {
    const res = await searchJobs({ page: 1, page_size: 100, hybrid: false });
    const jobRoutes = res.results.map((job) => ({
      url: `${SITE_URL}/jobs/${job.id}`,
      lastModified: job.posted_at ? new Date(job.posted_at) : new Date(),
      changeFrequency: "daily" as const,
      priority: 0.7,
    }));
    return [...staticRoutes, ...jobRoutes];
  } catch {
    return staticRoutes;
  }
}
