/**
 * SEO helpers: safe JSON-LD, JobPosting builders, indexability heuristics.
 * Never invent salary, location country, or employment type when unknown.
 */

import type { Job } from "@/lib/api/types";
import { SITE_URL } from "@/lib/api/client";

export const DEFAULT_FRESHNESS_DAYS = 30;

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

export function jobAgeDays(job: Pick<Job, "posted_at" | "first_seen_at">): number | null {
  const raw = job.posted_at || job.first_seen_at;
  if (!raw) return null;
  const t = new Date(raw).getTime();
  if (Number.isNaN(t)) return null;
  return Math.max(0, (Date.now() - t) / 86_400_000);
}

/** Fresh + active jobs are indexable; expired/inactive stay accessible but noindex. */
export function isJobIndexable(
  job: Pick<Job, "is_active" | "posted_at" | "first_seen_at">,
  freshnessDays: number = DEFAULT_FRESHNESS_DAYS,
): boolean {
  if (job.is_active === false) return false;
  const age = jobAgeDays(job);
  if (age == null) return true;
  return age <= freshnessDays + 0.5;
}

export function jobValidThroughIso(
  job: Pick<Job, "posted_at" | "first_seen_at">,
  freshnessDays: number = DEFAULT_FRESHNESS_DAYS,
): string | undefined {
  const raw = job.posted_at || job.first_seen_at;
  if (!raw) return undefined;
  const start = new Date(raw);
  if (Number.isNaN(start.getTime())) return undefined;
  const end = new Date(start.getTime() + freshnessDays * 86_400_000);
  return end.toISOString();
}

/** Map free-text employment to Schema.org / Google JobPosting enums. */
export function mapEmploymentType(raw?: string | null): string | string[] | undefined {
  if (!raw || !raw.trim()) return undefined;
  const n = raw.toLowerCase().replace(/[_-]+/g, " ").trim();
  const mapped: string[] = [];
  if (/\bfull[\s]?time\b|\bpermanent\b|\bfte\b/.test(n)) mapped.push("FULL_TIME");
  if (/\bpart[\s]?time\b/.test(n)) mapped.push("PART_TIME");
  if (/\bcontract\b|\bcontractor\b|\bfreelanc/.test(n)) mapped.push("CONTRACTOR");
  if (/\btemp(?:orary)?\b/.test(n)) mapped.push("TEMPORARY");
  if (/\bintern(?:ship)?\b/.test(n)) mapped.push("INTERN");
  if (/\bvolunteer\b/.test(n)) mapped.push("VOLUNTEER");
  if (!mapped.length) return undefined;
  return mapped.length === 1 ? mapped[0] : mapped;
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

export function buildJobPostingJsonLd(
  job: Job,
  opts?: { freshnessDays?: number; siteName?: string },
): Record<string, unknown> | null {
  if (!isJobIndexable(job, opts?.freshnessDays)) return null;

  const datePosted = job.posted_at || job.first_seen_at;
  if (!datePosted) return null;

  const org: Record<string, unknown> = {
    "@type": "Organization",
    name: job.company_name,
  };
  const sameAs = job.company_url || job.career_page_url;
  if (sameAs) org.sameAs = sameAs;

  const posting: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    title: job.title,
    description: descriptionToHtml(job.description_text, job.title),
    datePosted,
    hiringOrganization: org,
    identifier: {
      "@type": "PropertyValue",
      name: "Remote Atlas",
      value: String(job.id),
    },
    url: absoluteUrl(jobCanonicalPath(job.id)),
  };

  const validThrough = jobValidThroughIso(job, opts?.freshnessDays);
  if (validThrough) posting.validThrough = validThrough;

  const emp = mapEmploymentType(job.employment_type);
  if (emp) posting.employmentType = emp;

  const wt = (job.workplace_type || "").toLowerCase();
  if (wt === "remote") {
    posting.jobLocationType = "TELECOMMUTE";
    // Prefer real applicant region signals only when present in location_raw.
    const loc = (job.location_raw || "").trim();
    if (loc && !/worldwide|anywhere|global|remote/i.test(loc)) {
      posting.jobLocation = {
        "@type": "Place",
        address: {
          "@type": "PostalAddress",
          addressLocality: loc.slice(0, 120),
        },
      };
    }
  } else if (job.location_raw?.trim()) {
    posting.jobLocation = {
      "@type": "Place",
      address: {
        "@type": "PostalAddress",
        addressLocality: job.location_raw.trim().slice(0, 120),
      },
    };
  } else if (wt === "hybrid" || wt === "onsite") {
    // Location required for non-remote when known; omit rather than invent if empty.
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
  if (body) return `${lead}. ${body}`.slice(0, 160);
  return `${lead}. Fresh listing on Remote Atlas — apply on the employer’s official career page.`.slice(
    0,
    160,
  );
}

function titleSegment(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, " ");
}
