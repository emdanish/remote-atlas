import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/api";

/**
 * Crawl policy:
 * - Index: home, /jobs, /jobs/{id}, public SEO landings
 * - Block: account, workspace, auth, onboarding, hunt, API
 * - /seo/* is a Next rewrite target; leaked URLs 308 to /remote-{skill}-jobs
 * Faceted /jobs?* URLs are not disallowed (so share links resolve) but get
 * X-Robots-Tag: noindex via middleware + canonical to /jobs.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/profile",
          "/profile/",
          "/saved",
          "/saved/",
          "/matches",
          "/matches/",
          "/hunt",
          "/hunt/",
          "/alerts",
          "/alerts/",
          "/onboarding",
          "/onboarding/",
          "/login",
          "/login/",
          "/register",
          "/register/",
          "/api/",
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
