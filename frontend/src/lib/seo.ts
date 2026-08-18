/**
 * SEO helpers: safe JSON-LD, JobPosting builders, indexability heuristics.
 *
 * Never invent salary, street address, postal code, or employment type.
 * Google JobPosting: physical roles need Place + addressCountry; 100% remote
 * uses jobLocationType TELECOMMUTE + applicantLocationRequirements — not a
 * stub PostalAddress (that is what Search Console flagged as missing address*).
 */

import type { Job } from "@/lib/api/types";
import { SITE_URL } from "@/lib/api/client";

export const DEFAULT_FRESHNESS_DAYS = 30;

const US_STATE_TO_CODE: Record<string, string> = {
  alabama: "AL",
  alaska: "AK",
  arizona: "AZ",
  arkansas: "AR",
  california: "CA",
  colorado: "CO",
  connecticut: "CT",
  delaware: "DE",
  "district of columbia": "DC",
  florida: "FL",
  georgia: "GA",
  hawaii: "HI",
  idaho: "ID",
  illinois: "IL",
  indiana: "IN",
  iowa: "IA",
  kansas: "KS",
  kentucky: "KY",
  louisiana: "LA",
  maine: "ME",
  maryland: "MD",
  massachusetts: "MA",
  michigan: "MI",
  minnesota: "MN",
  mississippi: "MS",
  missouri: "MO",
  montana: "MT",
  nebraska: "NE",
  nevada: "NV",
  "new hampshire": "NH",
  "new jersey": "NJ",
  "new mexico": "NM",
  "new york": "NY",
  "north carolina": "NC",
  "north dakota": "ND",
  ohio: "OH",
  oklahoma: "OK",
  oregon: "OR",
  pennsylvania: "PA",
  "rhode island": "RI",
  "south carolina": "SC",
  "south dakota": "SD",
  tennessee: "TN",
  texas: "TX",
  utah: "UT",
  vermont: "VT",
  virginia: "VA",
  washington: "WA",
  "west virginia": "WV",
  wisconsin: "WI",
  wyoming: "WY",
};

const US_STATE_CODES = new Set(Object.values(US_STATE_TO_CODE));

const COUNTRY_NAME_TO_ISO: Record<string, string> = {
  usa: "US",
  us: "US",
  "united states": "US",
  "united states of america": "US",
  america: "US",
  uk: "GB",
  gb: "GB",
  "united kingdom": "GB",
  "great britain": "GB",
  england: "GB",
  scotland: "GB",
  wales: "GB",
  canada: "CA",
  ca: "CA",
  australia: "AU",
  au: "AU",
  germany: "DE",
  de: "DE",
  france: "FR",
  fr: "FR",
  netherlands: "NL",
  holland: "NL",
  nl: "NL",
  ireland: "IE",
  ie: "IE",
  india: "IN",
  in: "IN",
  pakistan: "PK",
  pk: "PK",
  singapore: "SG",
  sg: "SG",
  "united arab emirates": "AE",
  uae: "AE",
  ae: "AE",
  spain: "ES",
  es: "ES",
  italy: "IT",
  it: "IT",
  brazil: "BR",
  br: "BR",
  mexico: "MX",
  mx: "MX",
  japan: "JP",
  jp: "JP",
  poland: "PL",
  pl: "PL",
  portugal: "PT",
  pt: "PT",
  sweden: "SE",
  se: "SE",
  norway: "NO",
  no: "NO",
  denmark: "DK",
  dk: "DK",
  finland: "FI",
  fi: "FI",
  switzerland: "CH",
  ch: "CH",
  austria: "AT",
  at: "AT",
  belgium: "BE",
  be: "BE",
  "new zealand": "NZ",
  nz: "NZ",
  "south africa": "ZA",
  za: "ZA",
  philippines: "PH",
  ph: "PH",
  nigeria: "NG",
  ng: "NG",
  kenya: "KE",
  ke: "KE",
  bangladesh: "BD",
  bd: "BD",
  indonesia: "ID",
  id: "ID",
  malaysia: "MY",
  my: "MY",
  vietnam: "VN",
  vn: "VN",
  thailand: "TH",
  th: "TH",
  taiwan: "TW",
  tw: "TW",
  "hong kong": "HK",
  hk: "HK",
  israel: "IL",
  il: "IL",
  turkey: "TR",
  tr: "TR",
  ukraine: "UA",
  ua: "UA",
  romania: "RO",
  ro: "RO",
  argentina: "AR",
  ar: "AR",
  colombia: "CO",
  co: "CO",
  chile: "CL",
  cl: "CL",
  "south korea": "KR",
  korea: "KR",
  kr: "KR",
  egypt: "EG",
  eg: "EG",
  "saudi arabia": "SA",
  sa: "SA",
  qatar: "QA",
  qa: "QA",
  "czech republic": "CZ",
  czechia: "CZ",
  cz: "CZ",
};

const ISO_COUNTRY = new Set(Object.values(COUNTRY_NAME_TO_ISO));

const VAGUE_REMOTE = /^(remote|worldwide|anywhere|global|work from home|wfh|distributed|fully remote)$/i;

export type ParsedPostalAddress = {
  addressLocality?: string;
  addressRegion?: string;
  addressCountry: string;
};

/** Escape for embedding as application/ld+json script body (XSS-safe). */
export function safeJsonLd(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}

export function absoluteUrl(path: string): string {
  const base = SITE_URL.replace(/\/+$/, "");
  if (!path) return base;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export function jobCanonicalPath(jobId: number): string {
  return `/jobs/${jobId}`;
}

export function toIso8601(raw?: string | null): string | undefined {
  if (!raw) return undefined;
  const t = new Date(raw).getTime();
  if (Number.isNaN(t)) return undefined;
  return new Date(t).toISOString();
}

export function jobPostedRaw(
  job: Pick<Job, "posted_at" | "first_seen_at" | "last_seen_at">,
): string | null | undefined {
  return job.posted_at || job.first_seen_at || job.last_seen_at;
}

export function jobAgeDays(
  job: Pick<Job, "posted_at" | "first_seen_at" | "last_seen_at">,
): number | null {
  const raw = jobPostedRaw(job);
  if (!raw) return null;
  const t = new Date(raw).getTime();
  if (Number.isNaN(t)) return null;
  return Math.max(0, (Date.now() - t) / 86_400_000);
}

/** Fresh + active jobs are indexable; expired/inactive stay accessible but noindex. */
export function isJobIndexable(
  job: Pick<Job, "is_active" | "posted_at" | "first_seen_at" | "last_seen_at">,
  freshnessDays: number = DEFAULT_FRESHNESS_DAYS,
): boolean {
  if (job.is_active === false) return false;
  const age = jobAgeDays(job);
  if (age == null) return true;
  return age <= freshnessDays + 0.5;
}

export function jobValidThroughIso(
  job: Pick<Job, "posted_at" | "first_seen_at" | "last_seen_at">,
  freshnessDays: number = DEFAULT_FRESHNESS_DAYS,
): string | undefined {
  const startIso = toIso8601(jobPostedRaw(job));
  if (!startIso) return undefined;
  const start = new Date(startIso).getTime();
  return new Date(start + freshnessDays * 86_400_000).toISOString();
}

function lookupCountry(token: string): string | undefined {
  const n = token.toLowerCase().trim();
  if (!n) return undefined;
  if (n.length > 2) return COUNTRY_NAME_TO_ISO[n];
  const iso = n.toUpperCase();
  // Two-letter US states must not be read as ISO countries (CO, IN, CA, …).
  if (US_STATE_CODES.has(iso)) return undefined;
  if (ISO_COUNTRY.has(iso)) return iso;
  return COUNTRY_NAME_TO_ISO[n];
}

function lookupUsState(token: string): string | undefined {
  const n = token.toLowerCase().trim();
  if (!n) return undefined;
  if (n.length === 2 && US_STATE_CODES.has(n.toUpperCase())) return n.toUpperCase();
  return US_STATE_TO_CODE[n];
}

export function isVagueRemoteLocation(raw?: string | null): boolean {
  const n = (raw || "").replace(/\s+/g, " ").trim();
  if (!n) return true;
  return VAGUE_REMOTE.test(n);
}

/**
 * Parse source location text into a Google-valid PostalAddress.
 * Returns null unless addressCountry can be determined — never emit a Place
 * with only addressLocality (Search Console then asks for street/region/postal).
 * streetAddress and postalCode are omitted unless present in the source.
 */
export function parsePostalAddress(raw?: string | null): ParsedPostalAddress | null {
  let text = (raw || "").replace(/\s+/g, " ").trim();
  if (!text || isVagueRemoteLocation(text)) return null;
  text = text.replace(/^(remote|hybrid|onsite|on-site)[\s,;:/|-]+/i, "").trim();
  if (!text || isVagueRemoteLocation(text)) return null;

  const parts = text
    .split(/[,/|]/)
    .map((p) => p.replace(/\b\d{4,6}\b/g, "").trim())
    .filter(Boolean);
  if (!parts.length) return null;

  let addressCountry: string | undefined;
  let addressRegion: string | undefined;
  let addressLocality: string | undefined;
  const leftover: string[] = [];

  for (let i = parts.length - 1; i >= 0; i -= 1) {
    const part = parts[i];
    const country = lookupCountry(part);
    if (country && !addressCountry) {
      addressCountry = country;
      continue;
    }
    const state = lookupUsState(part);
    if (state && !addressRegion) {
      addressRegion = state;
      if (!addressCountry) addressCountry = "US";
      continue;
    }
    leftover.unshift(part);
  }

  if (!addressCountry && leftover.length === 1) {
    const only = leftover[0];
    const country = lookupCountry(only);
    if (country) {
      addressCountry = country;
      leftover.shift();
    }
  }

  if (leftover.length) {
    addressLocality = leftover.join(", ").slice(0, 80);
  }

  if (!addressCountry) return null;
  const out: ParsedPostalAddress = { addressCountry };
  if (addressLocality) out.addressLocality = addressLocality;
  if (addressRegion) out.addressRegion = addressRegion;
  return out;
}

function postalAddressJsonLd(addr: ParsedPostalAddress): Record<string, unknown> {
  const address: Record<string, unknown> = {
    "@type": "PostalAddress",
    addressCountry: addr.addressCountry,
  };
  if (addr.addressLocality) address.addressLocality = addr.addressLocality;
  if (addr.addressRegion) address.addressRegion = addr.addressRegion;
  return address;
}

const ISO_TO_GOOGLE_NAME: Record<string, string> = {
  US: "USA",
  GB: "United Kingdom",
  AE: "United Arab Emirates",
  KR: "South Korea",
  CZ: "Czechia",
  NZ: "New Zealand",
  ZA: "South Africa",
  HK: "Hong Kong",
};

function titleCaseCountryName(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => (w.length ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");
}

export function googleCountryName(iso: string): string {
  const code = iso.toUpperCase();
  if (ISO_TO_GOOGLE_NAME[code]) return ISO_TO_GOOGLE_NAME[code];
  const names = Object.entries(COUNTRY_NAME_TO_ISO)
    .filter(([, c]) => c === code)
    .map(([n]) => n)
    .filter((n) => n.length > 2);
  const best = names.sort((a, b) => b.length - a.length)[0];
  return best ? titleCaseCountryName(best) : code;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * ISO countries mentioned in source location text. Never infers a street.
 * Short ISO tokens (IN, CA, US) are ignored in free text to avoid false hits.
 */
export function parseApplicantCountryIsos(raw?: string | null): string[] {
  const isos = new Set<string>();
  const parsed = parsePostalAddress(raw);
  if (parsed?.addressCountry) isos.add(parsed.addressCountry);

  const text = (raw || "").toLowerCase();
  if (text) {
    const phrases = Object.entries(COUNTRY_NAME_TO_ISO)
      .filter(([name]) => name.length >= 4 || name === "usa" || name === "uae")
      .sort((a, b) => b[0].length - a[0].length);
    for (const [name, iso] of phrases) {
      const re = new RegExp(`(^|[^a-z])${escapeRegExp(name)}([^a-z]|$)`);
      if (re.test(text)) isos.add(iso);
    }
  }
  return [...isos];
}

export function applicantLocationRequirementsJsonLd(
  locRaw?: string | null,
): Record<string, string> | Array<Record<string, string>> {
  const isos = parseApplicantCountryIsos(locRaw);
  const countries = (isos.length ? isos : ["Worldwide"]).map((iso) =>
    iso === "Worldwide"
      ? { "@type": "Country", name: "Worldwide" }
      : { "@type": "Country", name: googleCountryName(iso) },
  );
  return countries.length === 1 ? countries[0] : countries;
}

/** Map free-text employment to Schema.org / Google JobPosting enums. */
export function mapEmploymentType(raw?: string | null): string | string[] | undefined {
  if (!raw || !raw.trim()) return undefined;
  const n = raw.toLowerCase().replace(/[_-]+/g, " ").trim();
  const mapped: string[] = [];
  if (/\bfull\s*time\b|\bpermanent\b|\bfte\b|\bfulltime\b/.test(n)) mapped.push("FULL_TIME");
  if (/\bpart\s*time\b|\bparttime\b/.test(n)) mapped.push("PART_TIME");
  if (/\bcontract\b|\bcontractor\b|\bfreelanc/.test(n)) mapped.push("CONTRACTOR");
  if (/\btemp(?:orary)?\b/.test(n)) mapped.push("TEMPORARY");
  if (/\bintern(?:ship)?\b/.test(n)) mapped.push("INTERN");
  if (/\bvolunteer\b/.test(n)) mapped.push("VOLUNTEER");
  if (/\bper\s*diem\b|\bother\b/.test(n) && !mapped.length) mapped.push("OTHER");
  if (!mapped.length) return undefined;
  return mapped.length === 1 ? mapped[0] : mapped;
}

/** Always emit a Google enum. Unmapped source text becomes OTHER — never invent FULL_TIME. */
export function jobEmploymentType(job: Pick<Job, "employment_type" | "career_stage">): string | string[] {
  const mapped = mapEmploymentType(job.employment_type);
  const internStage = (job.career_stage || "").toLowerCase() === "internship";
  if (internStage) {
    if (!mapped) return "INTERN";
    const list = Array.isArray(mapped) ? mapped : [mapped];
    if (!list.includes("INTERN")) return [...list, "INTERN"];
    return mapped;
  }
  return mapped ?? "OTHER";
}

/** Plain text → minimal safe HTML for JobPosting.description (Google accepts <br>/<p>). */
export function descriptionToHtml(text: string | null | undefined, fallback: string): string {
  const raw = (text || "").trim() || fallback;
  const escaped = raw
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
  const paragraphs = escaped
    .split(/\n{2,}/)
    .map((p) => `<p>${p.replace(/\n/g, "<br/>")}</p>`)
    .join("");
  return paragraphs || `<p>${escaped}</p>`;
}

export function jobHasThinDescription(job: Pick<Job, "title" | "description_text">): boolean {
  const text = (job.description_text || "").replace(/\s+/g, " ").trim();
  if (text.length < 60) return true;
  return text.toLowerCase() === (job.title || "").toLowerCase();
}

export function listingSummaryText(job: Job): string {
  const workplace =
    job.workplace_type && job.workplace_type !== "unknown"
      ? titleSegment(job.workplace_type)
      : "not specified by the source";
  return [
    `${job.title} at ${job.company_name}.`,
    job.location_raw ? `Location: ${job.location_raw}.` : null,
    job.employment_type ? `Employment: ${job.employment_type}.` : null,
    `Workplace: ${workplace}.`,
    job.workplace_type === "remote"
      ? "This role is listed as fully remote by the source."
      : null,
    "This listing is indexed from the employer’s official career system. Apply on the company page. Remote Atlas never submits applications.",
  ]
    .filter(Boolean)
    .join("\n\n");
}

export function jobPostingDescriptionHtml(job: Job): string {
  if (jobHasThinDescription(job)) {
    return descriptionToHtml(listingSummaryText(job), job.title);
  }
  return descriptionToHtml(job.description_text, job.title);
}

export function buildJobPostingJsonLd(
  job: Job,
  opts?: { freshnessDays?: number; siteName?: string },
): Record<string, unknown> | null {
  if (!isJobIndexable(job, opts?.freshnessDays)) return null;

  const datePosted = toIso8601(jobPostedRaw(job));
  if (!datePosted) return null;

  const org: Record<string, unknown> = {
    "@type": "Organization",
    name: job.company_name,
  };
  const sameAs = job.company_url || job.career_page_url;
  if (sameAs) org.sameAs = sameAs;
  if (job.company_url) org.url = job.company_url;

  const wt = (job.workplace_type || "").toLowerCase();
  const fullyRemote = wt === "remote";
  let description = jobPostingDescriptionHtml(job);
  if (fullyRemote && !/remote|work from home|telecommut|wfh/i.test(description)) {
    description = `<p>This role is listed as fully remote by the source.</p>${description}`;
  }

  const posting: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    title: job.title,
    description,
    datePosted,
    hiringOrganization: org,
    identifier: {
      "@type": "PropertyValue",
      name: job.company_name,
      value: job.external_id || String(job.id),
    },
    url: absoluteUrl(jobCanonicalPath(job.id)),
    inLanguage: "en",
    employmentType: jobEmploymentType(job),
  };

  const validThrough = jobValidThroughIso(job, opts?.freshnessDays);
  if (validThrough) posting.validThrough = validThrough;

  const parsed = parsePostalAddress(job.location_raw);
  const isHybrid = wt === "hybrid";
  const isOnsite = wt === "onsite";

  if (fullyRemote) {
    // Google: TELECOMMUTE jobs MUST name at least one applicant country.
    // Vague "Remote" / empty → Worldwide. Never invent a stub Place/street.
    posting.jobLocationType = "TELECOMMUTE";
    posting.applicantLocationRequirements = applicantLocationRequirementsJsonLd(
      job.location_raw,
    );
  } else if (isHybrid && parsed) {
    posting.jobLocation = {
      "@type": "Place",
      address: postalAddressJsonLd(parsed),
    };
  } else if (isHybrid) {
    posting.jobLocationType = "TELECOMMUTE";
    posting.applicantLocationRequirements = applicantLocationRequirementsJsonLd(
      job.location_raw,
    );
  } else if (parsed) {
    posting.jobLocation = {
      "@type": "Place",
      address: postalAddressJsonLd(parsed),
    };
  } else if (!isOnsite) {
    posting.jobLocationType = "TELECOMMUTE";
    posting.applicantLocationRequirements = applicantLocationRequirementsJsonLd(
      job.location_raw,
    );
  }

  if (job.years_required_min != null && job.years_required_min >= 0) {
    posting.experienceRequirements = {
      "@type": "OccupationalExperienceRequirements",
      monthsOfExperience: Math.round(job.years_required_min * 12),
    };
  }

  const skills = [...(job.skills || []), ...(job.tech_tags || [])]
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 24);
  if (skills.length) posting.skills = skills.join(", ");

  // directApply: only true if apply stays on Remote Atlas. Ours go external.
  posting.directApply = false;

  return posting;
}

export function buildBreadcrumbJsonLd(items: Array<{ name: string; path: string }>) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  };
}

export function buildCollectionJsonLd(opts: {
  name: string;
  path: string;
  description?: string;
  jobs: Array<Pick<Job, "id" | "title">>;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: opts.name,
    url: absoluteUrl(opts.path),
    ...(opts.description ? { description: opts.description } : {}),
    mainEntity: {
      "@type": "ItemList",
      numberOfItems: opts.jobs.length,
      itemListElement: opts.jobs.map((job, i) => ({
        "@type": "ListItem",
        position: i + 1,
        url: absoluteUrl(jobCanonicalPath(job.id)),
        name: job.title,
      })),
    },
  };
}

export function jobSeoTitle(job: Pick<Job, "title" | "company_name" | "workplace_type">): string {
  const workplace =
    job.workplace_type && job.workplace_type !== "unknown"
      ? titleSegment(job.workplace_type)
      : null;
  const base = `${job.title} at ${job.company_name}`;
  if (workplace) return `${base} — ${workplace}`;
  return base;
}

export function jobSeoDescription(job: Job): string {
  const bits = [
    job.title,
    job.company_name,
    job.workplace_type && job.workplace_type !== "unknown"
      ? titleSegment(job.workplace_type)
      : null,
    job.location_raw,
  ].filter(Boolean);
  const lead = bits.join(" · ");
  const body = (job.description_text || "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 140);
  if (body && body.toLowerCase() !== job.title.toLowerCase()) {
    return `${lead}. ${body}`.slice(0, 160);
  }
  return `${lead}. Fresh listing on Remote Atlas — apply on the employer’s official career page.`.slice(
    0,
    160,
  );
}

function titleSegment(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, " ");
}
