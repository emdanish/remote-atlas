import { API_URL } from "./client";

export type TitleSuggestion = { title: string; count: number };

export type SeoTaxonomyItem = {
  slug: string;
  label: string;
  count: number;
  kind: string;
  href: string;
};

export async function getTitleSuggestions(
  q: string,
  limit = 8,
): Promise<TitleSuggestion[]> {
  const qs = new URLSearchParams({ q, limit: String(limit) });
  const res = await fetch(`${API_URL}/jobs/title-suggestions?${qs}`, {
    headers: { Accept: "application/json" },
    next: { revalidate: 300 },
  });
  if (!res.ok) return [];
  const data = (await res.json()) as { suggestions?: TitleSuggestion[] };
  return data.suggestions || [];
}

export async function getSeoSkills(limit = 40): Promise<SeoTaxonomyItem[]> {
  const res = await fetch(`${API_URL}/jobs/seo/skills?limit=${limit}`, {
    headers: { Accept: "application/json" },
    next: { revalidate: 3600 },
  });
  if (!res.ok) return [];
  const data = (await res.json()) as { items?: SeoTaxonomyItem[] };
  return data.items || [];
}

export async function getSeoSkill(slug: string): Promise<SeoTaxonomyItem | null> {
  const res = await fetch(`${API_URL}/jobs/seo/skills/${encodeURIComponent(slug)}`, {
    headers: { Accept: "application/json" },
    next: { revalidate: 1800 },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`seo skill ${res.status}`);
  return res.json();
}

export async function getSeoCompanies(limit = 40): Promise<SeoTaxonomyItem[]> {
  const res = await fetch(`${API_URL}/jobs/seo/companies?limit=${limit}`, {
    headers: { Accept: "application/json" },
    next: { revalidate: 3600 },
  });
  if (!res.ok) return [];
  const data = (await res.json()) as { items?: SeoTaxonomyItem[] };
  return data.items || [];
}

export async function getSeoCompany(slug: string): Promise<SeoTaxonomyItem | null> {
  const res = await fetch(`${API_URL}/jobs/seo/companies/${encodeURIComponent(slug)}`, {
    headers: { Accept: "application/json" },
    next: { revalidate: 1800 },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`seo company ${res.status}`);
  return res.json();
}

export async function getSeoLocations(
  kind: "country" | "city",
): Promise<SeoTaxonomyItem[]> {
  const res = await fetch(`${API_URL}/jobs/seo/locations?kind=${kind}`, {
    headers: { Accept: "application/json" },
    next: { revalidate: 3600 },
  });
  if (!res.ok) return [];
  const data = (await res.json()) as { items?: SeoTaxonomyItem[] };
  return data.items || [];
}

export async function getSeoLocation(
  slug: string,
  kind: "country" | "city",
): Promise<SeoTaxonomyItem | null> {
  const res = await fetch(
    `${API_URL}/jobs/seo/locations/${encodeURIComponent(slug)}?kind=${kind}`,
    {
      headers: { Accept: "application/json" },
      next: { revalidate: 1800 },
    },
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`seo location ${res.status}`);
  return res.json();
}
