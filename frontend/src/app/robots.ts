import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/api";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/jobs", "/jobs/"],
        disallow: ["/profile", "/saved", "/matches", "/login", "/register", "/onboarding", "/alerts"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
