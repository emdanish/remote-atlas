import type { MetadataRoute } from "next";
import { getSitemapEntries, SITE_URL } from "@/lib/api";

/** Google sitemap limit is 50k URLs; keep jobs chunk under that with headroom for static. */
const JOBS_PER_SITEMAP = 5000;

export const revalidate = 3600;

/**
 * Number of sitemap chunks. id=0 is static pages + first job page;
 * higher ids are job-only chunks.
 */
export async function generateSitemaps() {
  try {
    const head = await getSitemapEntries(1, 1);
    const jobPages = Math.max(1, Math.ceil(head.total / JOBS_PER_SITEMAP));
    // Always emit at least 0; extra job shards are 1..jobPages-1 when needed
    const n = Math.max(1, jobPages);
    return Array.from({ length: n }, (_, id) => ({ id }));
  } catch {
    return [{ id: 0 }];
  }
}

export default async function sitemap(props: {
  id: number | Promise<number>;
}): Promise<MetadataRoute.Sitemap> {
  const id = await Promise.resolve(props.id);
  const staticRoutes: MetadataRoute.Sitemap =
    id === 0
      ? [
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
        ]
      : [];

  try {
    const page = id + 1; // API is 1-based
    const res = await getSitemapEntries(page, JOBS_PER_SITEMAP);
    const jobRoutes: MetadataRoute.Sitemap = res.entries.map((entry) => ({
      url: `${SITE_URL}/jobs/${entry.id}`,
      lastModified: entry.last_modified ? new Date(entry.last_modified) : new Date(),
      changeFrequency: "daily" as const,
      priority: 0.7,
    }));
    return [...staticRoutes, ...jobRoutes];
  } catch {
    return staticRoutes;
  }
}
