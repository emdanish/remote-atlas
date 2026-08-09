import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/api";

/**
 * Crawl policy:
 * - Index: home, base /jobs discovery, individual /jobs/{id}
 * - Block: account, workspace, auth, onboarding
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
