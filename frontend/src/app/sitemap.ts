import type { MetadataRoute } from "next";
import { getSitemapEntries, SITE_URL } from "@/lib/api";

/**
 * Single metadata route at /sitemap.xml (Next.js 15 Metadata API).
 *
 * Important: do NOT use generateSitemaps() here — that maps only to
 * /sitemap/[id].xml and leaves /sitemap.xml as 404 in production.
 *
 * Google limit: 50,000 URLs per sitemap. We page the sitemap-entries API
 * until empty or that cap (today's index is well under it).
 */
const PAGE_SIZE = 5000;
const MAX_URLS = 50_000;

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticRoutes: MetadataRoute.Sitemap = [
    {
      url: SITE_URL,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 1,
    },
    {
      url: `${SITE_URL}/jobs`,
      lastModified: new Date(),
      changeFrequency: "hourly",
      priority: 0.9,
    },
  ];

  const jobRoutes: MetadataRoute.Sitemap = [];

  try {
    let page = 1;
    let total = Infinity;

    while (jobRoutes.length + staticRoutes.length < MAX_URLS) {
      const remaining = MAX_URLS - staticRoutes.length - jobRoutes.length;
      const pageSize = Math.min(PAGE_SIZE, remaining);
      if (pageSize <= 0) break;

      const res = await getSitemapEntries(page, pageSize);
      total = res.total;

      for (const entry of res.entries) {
        jobRoutes.push({
          url: `${SITE_URL}/jobs/${entry.id}`,
          lastModified: entry.last_modified
            ? new Date(entry.last_modified)
            : new Date(),
          changeFrequency: "daily",
          priority: 0.7,
        });
      }

      if (!res.entries.length) break;
      if (page * pageSize >= total) break;
      page += 1;
      // Safety: avoid pathological loops
      if (page > 20) break;
    }
  } catch {
    // Sitemap still returns core public routes if the API is briefly down.
  }

  return [...staticRoutes, ...jobRoutes];
}
