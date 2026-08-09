import { API_URL } from "./client";

export type SitemapJobEntry = {
  id: number;
  last_modified: string;
};

export type SitemapEntriesResponse = {
  total: number;
  page: number;
  page_size: number;
  freshness_days: number;
  entries: SitemapJobEntry[];
};

/** Server-only: lightweight job IDs for XML sitemaps. */
export async function getSitemapEntries(
  page = 1,
  pageSize = 5000,
): Promise<SitemapEntriesResponse> {
  const qs = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  const res = await fetch(`${API_URL}/jobs/sitemap-entries?${qs}`, {
    headers: { Accept: "application/json" },
    next: { revalidate: 3600 },
  });
  if (!res.ok) {
    throw new Error(`sitemap-entries failed: ${res.status}`);
  }
  return res.json() as Promise<SitemapEntriesResponse>;
}
