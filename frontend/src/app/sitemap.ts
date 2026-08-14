import type { MetadataRoute } from "next";
import {
  getSeoCompanies,
  getSeoLocations,
  getSeoSkills,
  getSitemapEntries,
  SITE_URL,
} from "@/lib/api";

/**
 * Single /sitemap.xml: static hubs + quality SEO landings + fresh jobs.
 * Faceted /jobs?* URLs are intentionally omitted (noindex via middleware).
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
    {
      url: `${SITE_URL}/remote-junior-jobs`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.85,
    },
    {
      url: `${SITE_URL}/remote-internships`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.85,
    },
    {
      url: `${SITE_URL}/companies`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.75,
    },
  ];

  const seoRoutes: MetadataRoute.Sitemap = [];
  try {
    const [skills, companies, countries, cities] = await Promise.all([
      getSeoSkills(120),
      getSeoCompanies(120),
      getSeoLocations("country"),
      getSeoLocations("city"),
    ]);
    for (const s of skills) {
      seoRoutes.push({
        url: `${SITE_URL}${s.href}`,
        lastModified: new Date(),
        changeFrequency: "daily",
        priority: 0.8,
      });
    }
    for (const c of companies) {
      seoRoutes.push({
        url: `${SITE_URL}${c.href}`,
        lastModified: new Date(),
        changeFrequency: "daily",
        priority: 0.75,
      });
    }
    for (const loc of [...countries, ...cities]) {
      seoRoutes.push({
        url: `${SITE_URL}${loc.href}`,
        lastModified: new Date(),
        changeFrequency: "daily",
        priority: 0.75,
      });
    }
  } catch {
    /* keep sitemap usable without taxonomy */
  }

  const jobRoutes: MetadataRoute.Sitemap = [];
  try {
    let page = 1;
    let total = Infinity;
    const headroom = MAX_URLS - staticRoutes.length - seoRoutes.length;

    while (jobRoutes.length < headroom) {
      const remaining = headroom - jobRoutes.length;
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
      if (page > 20) break;
    }
  } catch {
    /* static + seo still useful */
  }

  return [...staticRoutes, ...seoRoutes, ...jobRoutes];
}
